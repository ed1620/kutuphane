from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from ..models import db, Masa, Rezervasyon
from config import Config

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.tanitim'))


@main_bp.route('/tanitim')
def tanitim():
    return render_template('tanitim.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    from ..utils import doluluk_istatistigi

    # Kat bazlı masa verisi
    katlar = {}
    masalar = Masa.query.order_by(Masa.kat, Masa.bolge, Masa.masa_kodu).all()
    for masa in masalar:
        if masa.kat not in katlar:
            katlar[masa.kat] = {}
        if masa.bolge not in katlar[masa.kat]:
            katlar[masa.kat][masa.bolge] = []
        katlar[masa.kat][masa.bolge].append(masa)

    istatistik = doluluk_istatistigi()

    aktif_rez = Rezervasyon.query.filter_by(
        kullanici_id=current_user.id,
        durum='aktif'
    ).first()

    mola_rez = Rezervasyon.query.filter_by(
        kullanici_id=current_user.id,
        durum='molada'
    ).first()

    simdi = datetime.utcnow()

    # 30 dakika geçti mi? (mola hakkı)
    mola_hakki = False
    if aktif_rez:
        gecen_sure = (simdi - aktif_rez.giris_zamani).total_seconds() / 60
        mola_hakki = gecen_sure >= Config.MIN_SURE_MOLA_DK

    return render_template('dashboard.html',
                           katlar=katlar,
                           istatistik=istatistik,
                           aktif_rez=aktif_rez,
                           mola_rez=mola_rez,
                           mola_hakki=mola_hakki,
                           simdi=simdi,
                           config=Config)


@main_bp.route('/masa/<masa_kodu>')
@login_required
def masa_detay(masa_kodu):
    """QR kodun yönlendirdiği sayfa: check-in, doğrulama veya moladan dönüş."""
    masa = Masa.query.filter_by(masa_kodu=masa_kodu).first_or_404()
    simdi = datetime.utcnow()

    # Kullanıcının bu masadaki aktif/molada rezervasyonu
    kendi_rez = Rezervasyon.query.filter(
        Rezervasyon.kullanici_id == current_user.id,
        Rezervasyon.masa_id == masa.id,
        Rezervasyon.durum.in_(['aktif', 'molada'])
    ).first()

    # Kullanıcının başka masadaki aktif/molada rezervasyonu
    diger_rez = None
    if not kendi_rez:
        diger_rez = Rezervasyon.query.filter(
            Rezervasyon.kullanici_id == current_user.id,
            Rezervasyon.durum.in_(['aktif', 'molada'])
        ).first()

    aksiyon = _aksiyon_belirle(masa, kendi_rez, diger_rez, simdi)

    # QR taraması olmadan check-in/doğrulama yapılamaz
    if aksiyon in ('checkin', 'mola_donus', 'dogrulama_gerekli'):
        qr = session.get('qr_scan', {})
        gecerli = (
            qr.get('masa') == masa_kodu and
            (simdi.timestamp() - qr.get('ts', 0)) < 300  # 5 dakika geçerli
        )
        if not gecerli:
            flash('Bu masaya check-in yapabilmek için masanın QR kodunu tarayın.', 'warning')
            return redirect(url_for('main.qr_tara'))

    return render_template('masa_detay.html',
                           masa=masa,
                           kendi_rez=kendi_rez,
                           aksiyon=aksiyon,
                           simdi=simdi,
                           config=Config)


def _aksiyon_belirle(masa, kendi_rez, diger_rez, simdi):
    """Masada yapılabilecek aksiyonu belirle."""
    if kendi_rez:
        if kendi_rez.durum == 'molada':
            if simdi > kendi_rez.bitis_zamani:
                return 'mola_suresi_doldu'
            return 'mola_donus'
        if kendi_rez.dogrulama_bekleniyor:
            return 'dogrulama_gerekli'
        return 'zaten_oturuyorsun'
    if diger_rez:
        return 'baska_masada'
    if masa.durum == 'bos':
        return 'checkin'
    return 'dolu'


@main_bp.route('/masa/<masa_kodu>/giris', methods=['POST'])
@login_required
def checkin(masa_kodu):
    """Masaya otur (QR tarama sonrası form POST)."""
    masa = Masa.query.filter_by(masa_kodu=masa_kodu).first_or_404()

    # Moladan dönüş mu?
    mola_rez = Rezervasyon.query.filter(
        Rezervasyon.kullanici_id == current_user.id,
        Rezervasyon.masa_id == masa.id,
        Rezervasyon.durum == 'molada'
    ).first()

    simdi = datetime.utcnow()

    if mola_rez:
        if simdi > mola_rez.bitis_zamani:
            mola_rez.durum = 'otomatik_iptal'
            mola_rez.cikis_zamani = simdi
            masa.durum = 'bos'
            db.session.commit()
            flash('Mola süreniz doldu. Masanız serbest bırakıldı.', 'danger')
            return redirect(url_for('main.dashboard'))

        mola_rez.durum = 'aktif'
        mola_rez.bitis_zamani = simdi + timedelta(minutes=Config.MAX_OTURMA_SURESI_DK)
        mola_rez.mola_turu = None
        mola_rez.son_dogrulama = simdi
        mola_rez.dogrulama_bekleniyor = False
        mola_rez.dogrulama_bitis = None
        masa.durum = 'dolu'
        db.session.commit()
        flash('Moladan döndünüz. İyi çalışmalar!', 'success')
        return redirect(url_for('main.dashboard'))

    # Periyodik doğrulama mu?
    aktif_rez = Rezervasyon.query.filter(
        Rezervasyon.kullanici_id == current_user.id,
        Rezervasyon.masa_id == masa.id,
        Rezervasyon.durum == 'aktif',
        Rezervasyon.dogrulama_bekleniyor == True
    ).first()

    if aktif_rez:
        aktif_rez.son_dogrulama = simdi
        aktif_rez.dogrulama_bekleniyor = False
        aktif_rez.dogrulama_bitis = None
        db.session.commit()
        flash('Varlığınız doğrulandı. İyi çalışmalar!', 'success')
        return redirect(url_for('main.dashboard'))

    # Yeni check-in
    if masa.durum != 'bos':
        flash(f'Masa {masa_kodu} şu anda müsait değil.', 'warning')
        return redirect(url_for('main.dashboard'))

    var_olan = Rezervasyon.query.filter(
        Rezervasyon.kullanici_id == current_user.id,
        Rezervasyon.durum.in_(['aktif', 'molada'])
    ).first()
    if var_olan:
        flash('Zaten aktif bir rezervasyonunuz var. Önce çıkış yapın.', 'warning')
        return redirect(url_for('main.dashboard'))

    bitis = simdi + timedelta(minutes=Config.MAX_OTURMA_SURESI_DK)

    rez = Rezervasyon(
        kullanici_id=current_user.id,
        masa_id=masa.id,
        giris_zamani=simdi,
        bitis_zamani=bitis,
        durum='aktif',
        son_dogrulama=simdi,
        dogrulama_bekleniyor=False
    )
    masa.durum = 'dolu'
    db.session.add(rez)
    db.session.commit()

    session.pop('qr_scan', None)
    flash(f'Masa {masa_kodu} rezervasyonu başarılı!', 'success')
    return redirect(url_for('main.dashboard'))


@main_bp.route('/mola/<mola_turu>')
@login_required
def mola_baslat(mola_turu):
    """Mola başlat. mola_turu: 'normal' (15dk) veya 'yemek' (60dk)."""
    if mola_turu not in ('normal', 'yemek'):
        flash('Geçersiz mola türü.', 'danger')
        return redirect(url_for('main.dashboard'))

    rez = Rezervasyon.query.filter_by(
        kullanici_id=current_user.id,
        durum='aktif'
    ).first()

    if not rez:
        flash('Aktif rezervasyonunuz bulunmuyor.', 'warning')
        return redirect(url_for('main.dashboard'))

    simdi = datetime.utcnow()

    # 30 dakika kuralı
    gecen_sure_dk = (simdi - rez.giris_zamani).total_seconds() / 60
    if gecen_sure_dk < Config.MIN_SURE_MOLA_DK:
        kalan = int(Config.MIN_SURE_MOLA_DK - gecen_sure_dk) + 1
        flash(f'Mola almak için {kalan} dakika daha beklemeniz gerekiyor.', 'warning')
        return redirect(url_for('main.dashboard'))

    sure_dk = Config.YEMEK_MOLA_DK if mola_turu == 'yemek' else Config.NORMAL_MOLA_DK
    sure_adi = 'Yemek molası (60 dk)' if mola_turu == 'yemek' else 'Normal mola (15 dk)'

    rez.durum = 'molada'
    rez.mola_turu = mola_turu
    rez.mola_baslangic = simdi
    rez.cikis_zamani = simdi
    rez.bitis_zamani = simdi + timedelta(minutes=sure_dk)
    rez.dogrulama_bekleniyor = False

    masa = Masa.query.get(rez.masa_id)
    masa.durum = 'molada'
    db.session.commit()

    flash(f'{sure_adi} başlatıldı. Zamanında dönmezseniz masanız serbest bırakılır.', 'info')
    return redirect(url_for('main.dashboard'))


@main_bp.route('/cikis-yap')
@login_required
def cikis_yap():
    rez = Rezervasyon.query.filter(
        Rezervasyon.kullanici_id == current_user.id,
        Rezervasyon.durum.in_(['aktif', 'molada'])
    ).first()

    if not rez:
        flash('Aktif rezervasyonunuz bulunmuyor.', 'warning')
        return redirect(url_for('main.dashboard'))

    rez.durum = 'tamamlandi'
    rez.cikis_zamani = datetime.utcnow()
    masa = Masa.query.get(rez.masa_id)
    masa.durum = 'bos'
    db.session.commit()

    flash('Çıkış yapıldı. Görüşmek üzere!', 'success')
    return redirect(url_for('main.dashboard'))


@main_bp.route('/qr-tara')
@login_required
def qr_tara():
    return render_template('qr_tara.html')


@main_bp.route('/qr-panel')
def qr_panel():
    """Giriş gerektirmeyen bağımsız QR test paneli."""
    masalar = Masa.query.order_by(Masa.kat, Masa.bolge, Masa.masa_kodu).all()
    return render_template('qr_panel.html', masalar=masalar)


@main_bp.route('/gecmis')
@login_required
def gecmis():
    rezervasyonlar = Rezervasyon.query.filter_by(
        kullanici_id=current_user.id
    ).order_by(Rezervasyon.giris_zamani.desc()).limit(20).all()
    return render_template('gecmis.html', rezervasyonlar=rezervasyonlar)
