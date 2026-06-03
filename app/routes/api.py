from flask import Blueprint, jsonify, request, session
from flask_login import login_required, current_user
from datetime import datetime
from ..models import Masa, Rezervasyon, db
from ..utils import doluluk_istatistigi

api_bp = Blueprint('api', __name__)


@api_bp.route('/masalar')
def masalar():
    """Tüm masaların durumu (giriş gerektirmez — uzaktan izleme için)."""
    tum_masalar = Masa.query.order_by(Masa.kat, Masa.bolge, Masa.masa_kodu).all()
    return jsonify([{
        'id': m.id,
        'masa_kodu': m.masa_kodu,
        'kat': m.kat,
        'bolge': m.bolge,
        'bolge_turu': m.bolge_turu,
        'durum': m.durum,
        'qr': m.qr_resim_yolu
    } for m in tum_masalar])


@api_bp.route('/kat/<int:kat_no>/masalar')
def kat_masalari(kat_no):
    """Belirli kattaki masalar."""
    masalar = Masa.query.filter_by(kat=kat_no).order_by(Masa.bolge, Masa.masa_kodu).all()
    return jsonify([{
        'id': m.id,
        'masa_kodu': m.masa_kodu,
        'bolge': m.bolge,
        'bolge_turu': m.bolge_turu,
        'durum': m.durum
    } for m in masalar])


@api_bp.route('/istatistik')
def istatistik():
    """Anlık doluluk istatistikleri."""
    return jsonify(doluluk_istatistigi())


@api_bp.route('/kat-istatistik')
def kat_istatistik():
    """Kat bazlı doluluk istatistikleri."""
    katlar = db.session.query(Masa.kat).distinct().order_by(Masa.kat).all()
    sonuc = {}
    for (kat_no,) in katlar:
        masalar = Masa.query.filter_by(kat=kat_no).all()
        toplam = len(masalar)
        dolu = sum(1 for m in masalar if m.durum == 'dolu')
        molada = sum(1 for m in masalar if m.durum == 'molada')
        bos = sum(1 for m in masalar if m.durum == 'bos')
        sonuc[str(kat_no)] = {
            'toplam': toplam,
            'dolu': dolu,
            'molada': molada,
            'bos': bos,
            'doluluk_orani': round((dolu + molada) / toplam * 100, 1) if toplam > 0 else 0
        }
    return jsonify(sonuc)


@api_bp.route('/rezervasyon/<int:rezervasyon_id>/kalan-sure')
@login_required
def kalan_sure(rezervasyon_id):
    rez = Rezervasyon.query.get_or_404(rezervasyon_id)
    simdi = datetime.utcnow()
    kalan_saniye = max(0, int((rez.bitis_zamani - simdi).total_seconds()))
    return jsonify({
        'kalan_saniye': kalan_saniye,
        'kalan_dakika': kalan_saniye // 60,
        'durum': rez.durum,
        'dogrulama_bekleniyor': rez.dogrulama_bekleniyor or False
    })


@api_bp.route('/dogrulama-durumu')
@login_required
def dogrulama_durumu():
    """Kullanıcının aktif rezervasyonunda doğrulama beklenip beklenmediği."""
    rez = Rezervasyon.query.filter_by(
        kullanici_id=current_user.id,
        durum='aktif'
    ).first()

    if not rez:
        return jsonify({'bekleniyor': False})

    simdi = datetime.utcnow()
    bitis_saniye = None
    if rez.dogrulama_bekleniyor and rez.dogrulama_bitis:
        bitis_saniye = max(0, int((rez.dogrulama_bitis - simdi).total_seconds()))

    return jsonify({
        'bekleniyor': rez.dogrulama_bekleniyor or False,
        'masa_kodu': rez.masa.masa_kodu,
        'kalan_saniye': bitis_saniye
    })


@api_bp.route('/bluetooth-beacon-ismi')
@login_required
def bluetooth_beacon_ismi():
    """Masanın beklenen BLE beacon adını döner (tarayıcıda tarama için)."""
    masa_kodu = request.args.get('masa_kodu', '')
    masa = Masa.query.filter_by(masa_kodu=masa_kodu).first()
    if not masa:
        return jsonify({'hata': 'Masa bulunamadı'}), 404
    return jsonify({
        'masa_kodu': masa.masa_kodu,
        'bluetooth_isim': masa.bluetooth_isim or f'KUT-{masa.masa_kodu}'
    })


@api_bp.route('/bluetooth-dogrula', methods=['POST'])
@login_required
def bluetooth_dogrula():
    """Bluetooth beacon tarama sonucuyla varlık doğrulama.

    Beklenen JSON:
    {
        "masa_kodu": "K1-S01",
        "bulunan_cihaz_adi": "KUT-K1-S01",  # tarayıcının bulduğu beacon adı
        "rssi": -65                           # sinyal gücü (dBm), opsiyonel
    }
    """
    data = request.get_json() or {}
    masa_kodu = data.get('masa_kodu', '')
    bulunan_cihaz = data.get('bulunan_cihaz_adi', '')
    rssi = data.get('rssi')  # sinyal gücü, opsiyonel

    masa = Masa.query.filter_by(masa_kodu=masa_kodu).first()
    if not masa:
        return jsonify({'basarili': False, 'mesaj': 'Masa bulunamadı.'})

    beklenen_beacon = masa.bluetooth_isim or f'KUT-{masa.masa_kodu}'

    # Bulunan cihaz adı masanın beacon'ıyla eşleşiyor mu?
    if bulunan_cihaz != beklenen_beacon:
        return jsonify({
            'basarili': False,
            'mesaj': f'Yanlış beacon: "{bulunan_cihaz}" bulundu, "{beklenen_beacon}" bekleniyor.'
        })

    # RSSI kontrolü: çok uzakta değil mi? (isteğe bağlı, -80 dBm'den zayıfsa reddet)
    if rssi is not None and rssi < -85:
        return jsonify({
            'basarili': False,
            'mesaj': f'Beacon çok uzakta (RSSI: {rssi} dBm). Masaya daha yakın olun.'
        })

    # Rezervasyon kontrolü — check-in veya doğrulama için
    rez = Rezervasyon.query.filter(
        Rezervasyon.kullanici_id == current_user.id,
        Rezervasyon.masa_id == masa.id,
        Rezervasyon.durum.in_(['aktif', 'molada'])
    ).first()

    if not rez:
        return jsonify({'basarili': False, 'mesaj': 'Bu masada aktif rezervasyonunuz yok.'})

    simdi = datetime.utcnow()
    rez.son_dogrulama = simdi
    rez.dogrulama_bekleniyor = False
    rez.dogrulama_bitis = None
    db.session.commit()

    rssi_bilgi = f' (RSSI: {rssi} dBm)' if rssi is not None else ''
    return jsonify({
        'basarili': True,
        'mesaj': f'✅ Beacon doğrulandı{rssi_bilgi}. Kütüphanede olduğunuz teyit edildi.'
    })


@api_bp.route('/qr-onayla', methods=['POST'])
@login_required
def qr_onayla():
    """QR kod taranınca session'a kısa süreli token yaz."""
    data = request.get_json() or {}
    masa_kodu = data.get('masa_kodu', '').strip()
    masa = Masa.query.filter_by(masa_kodu=masa_kodu).first()
    if not masa:
        return jsonify({'basarili': False, 'mesaj': 'Masa bulunamadı.'})
    session['qr_scan'] = {'masa': masa_kodu, 'ts': datetime.utcnow().timestamp()}
    return jsonify({'basarili': True, 'yonlendir': f'/masa/{masa_kodu}'})


@api_bp.route('/doluluk-gecmisi')
def doluluk_gecmisi():
    """Son 7 günün saatlik doluluk verisi."""
    from datetime import timedelta
    simdi = datetime.utcnow()
    yedi_gun_once = simdi - timedelta(days=7)

    rezervasyonlar = Rezervasyon.query.filter(
        Rezervasyon.giris_zamani >= yedi_gun_once
    ).all()

    saat_sayilari = [0] * 24
    for r in rezervasyonlar:
        saat = r.giris_zamani.hour
        saat_sayilari[saat] += 1

    return jsonify({
        'saatler': list(range(24)),
        'sayilar': saat_sayilari,
        'en_yogun_saat': saat_sayilari.index(max(saat_sayilari)) if max(saat_sayilari) > 0 else None
    })
