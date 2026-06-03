from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from ..models import db, Masa, Rezervasyon, Kullanici
import os

admin_bp = Blueprint('admin', __name__)

def admin_gerekli(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.rol != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated

@admin_bp.route('/')
@login_required
@admin_gerekli
def panel():
    from ..utils import grafik_olustur, doluluk_istatistigi
    from flask import current_app

    masalar    = Masa.query.order_by(Masa.kat, Masa.bolge, Masa.masa_kodu).all()
    istatistik = doluluk_istatistigi()
    grafik     = grafik_olustur(current_app._get_current_object())

    son_rezervasyonlar = Rezervasyon.query.order_by(
        Rezervasyon.giris_zamani.desc()
    ).limit(15).all()

    toplam_kullanici = Kullanici.query.filter_by(rol='ogrenci').count()
    bugun_baslangic  = datetime.utcnow().replace(hour=0, minute=0, second=0)
    bugun_rezervasyon = Rezervasyon.query.filter(
        Rezervasyon.giris_zamani >= bugun_baslangic
    ).count()

    dogrulama_bekleyen = Rezervasyon.query.filter_by(
        durum='aktif',
        dogrulama_bekleniyor=True
    ).count()

    # Kat bazlı özet
    katlar = db.session.query(Masa.kat).distinct().order_by(Masa.kat).all()
    kat_ozet = {}
    for (kat_no,) in katlar:
        tum = Masa.query.filter_by(kat=kat_no).all()
        kat_ozet[kat_no] = {
            'toplam': len(tum),
            'dolu': sum(1 for m in tum if m.durum == 'dolu'),
            'molada': sum(1 for m in tum if m.durum == 'molada'),
            'bos': sum(1 for m in tum if m.durum == 'bos'),
        }

    return render_template('admin.html',
                           masalar=masalar,
                           istatistik=istatistik,
                           grafik=grafik,
                           son_rezervasyonlar=son_rezervasyonlar,
                           toplam_kullanici=toplam_kullanici,
                           bugun_rezervasyon=bugun_rezervasyon,
                           dogrulama_bekleyen=dogrulama_bekleyen,
                           kat_ozet=kat_ozet)

@admin_bp.route('/masa-sifirla/<int:masa_id>')
@login_required
@admin_gerekli
def masa_sifirla(masa_id):
    masa = Masa.query.get_or_404(masa_id)
    aktif_rez = Rezervasyon.query.filter(
        Rezervasyon.masa_id == masa_id,
        Rezervasyon.durum.in_(['aktif', 'molada'])
    ).first()
    if aktif_rez:
        aktif_rez.durum = 'iptal'
        aktif_rez.cikis_zamani = datetime.utcnow()
    masa.durum = 'bos'
    db.session.commit()
    flash(f'Masa {masa.masa_kodu} sıfırlandı.', 'success')
    return redirect(url_for('admin.panel'))

@admin_bp.route('/kullanicilar')
@login_required
@admin_gerekli
def kullanicilar():
    liste = Kullanici.query.order_by(Kullanici.olusturulma.desc()).all()
    return render_template('kullanicilar.html', kullanicilar=liste)


@admin_bp.route('/qr-kodlar')
@login_required
@admin_gerekli
def qr_kodlar():
    masalar = Masa.query.order_by(Masa.kat, Masa.bolge, Masa.masa_kodu).all()
    sunucu_url = request.host_url.rstrip('/')
    return render_template('admin_qr.html', masalar=masalar, sunucu_url=sunucu_url)


@admin_bp.route('/qr-yenile', methods=['POST'])
@login_required
@admin_gerekli
def qr_yenile():
    import qrcode
    masalar = Masa.query.all()
    qr_klasor = os.path.join(current_app.static_folder, 'qrcodes')
    os.makedirs(qr_klasor, exist_ok=True)
    base_url = request.host_url.rstrip('/')
    for masa in masalar:
        qr_yolu = os.path.join(qr_klasor, f'{masa.masa_kodu}.png')
        qr = qrcode.QRCode(version=1, box_size=8, border=2)
        qr.add_data(f'{base_url}/masa/{masa.masa_kodu}')
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        img.save(qr_yolu)
        masa.qr_resim_yolu = f'qrcodes/{masa.masa_kodu}.png'
    db.session.commit()
    flash(f'{len(masalar)} adet QR kod başarıyla yenilendi ({base_url}).', 'success')
    return redirect(url_for('admin.qr_kodlar'))


@admin_bp.route('/qr-test')
@login_required
@admin_gerekli
def qr_test():
    """Kroki harita üzerinde QR kodları test et."""
    katlar = {}
    masalar = Masa.query.order_by(Masa.kat, Masa.bolge, Masa.masa_kodu).all()
    for masa in masalar:
        if masa.kat not in katlar:
            katlar[masa.kat] = {}
        if masa.bolge not in katlar[masa.kat]:
            katlar[masa.kat][masa.bolge] = []
        katlar[masa.kat][masa.bolge].append(masa)
    return render_template('qr_test.html', katlar=katlar)


@admin_bp.route('/ogrenci-rezervasyon', methods=['POST'])
@login_required
@admin_gerekli
def ogrenci_rezervasyon():
    """Admin, öğrenci ID'si girerek manuel masa rezervasyonu oluşturur."""
    from config import Config
    ogrenci_no = request.form.get('ogrenci_no', '').strip()
    masa_id = request.form.get('masa_id', type=int)

    ogrenci = Kullanici.query.filter_by(ogrenci_no=ogrenci_no, rol='ogrenci').first()
    if not ogrenci:
        flash(f'"{ogrenci_no}" numaralı öğrenci bulunamadı.', 'danger')
        return redirect(url_for('admin.panel'))

    masa = Masa.query.get_or_404(masa_id)
    if masa.durum != 'bos':
        flash(f'Masa {masa.masa_kodu} şu anda müsait değil.', 'warning')
        return redirect(url_for('admin.panel'))

    var_olan = Rezervasyon.query.filter(
        Rezervasyon.kullanici_id == ogrenci.id,
        Rezervasyon.durum.in_(['aktif', 'molada'])
    ).first()
    if var_olan:
        flash(f'{ogrenci.ad_soyad} adlı öğrencinin zaten aktif bir rezervasyonu var (Masa {var_olan.masa.masa_kodu}).', 'warning')
        return redirect(url_for('admin.panel'))

    simdi = datetime.utcnow()
    bitis = simdi + timedelta(minutes=Config.MAX_OTURMA_SURESI_DK)
    rez = Rezervasyon(
        kullanici_id=ogrenci.id,
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
    flash(f'✅ {ogrenci.ad_soyad} ({ogrenci_no}) için Masa {masa.masa_kodu} rezervasyonu oluşturuldu.', 'success')
    return redirect(url_for('admin.panel'))


@admin_bp.route('/rezervasyon-sonlandir/<int:rez_id>', methods=['POST'])
@login_required
@admin_gerekli
def rezervasyon_sonlandir(rez_id):
    """Belirli bir aktif rezervasyonu admin olarak sonlandır."""
    rez = Rezervasyon.query.get_or_404(rez_id)
    if rez.durum in ('aktif', 'molada'):
        rez.durum = 'iptal'
        rez.cikis_zamani = datetime.utcnow()
        rez.masa.durum = 'bos'
        db.session.commit()
        flash(f'{rez.kullanici.ad_soyad} — Masa {rez.masa.masa_kodu} rezervasyonu sonlandırıldı.', 'success')
    return redirect(url_for('admin.panel'))
