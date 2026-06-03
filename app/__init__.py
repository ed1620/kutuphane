from flask import Flask
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from .models import db, Kullanici, Masa
from config import Config
from datetime import datetime, timedelta
import os

bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = 'auth.giris'
login_manager.login_message = 'Bu sayfaya erişmek için giriş yapmalısınız.'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def kullanici_yukle(kullanici_id):
    return Kullanici.query.get(int(kullanici_id))

def uygulama_olustur():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(Config)

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # Blueprint'leri kaydet
    from .routes.auth import auth_bp
    from .routes.main import main_bp
    from .routes.admin import admin_bp
    from .routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')

    with app.app_context():
        db.create_all()
        ornek_veri_olustur(app)

    # Zamanlayıcıyı başlat
    from .scheduler import zamanlayici_baslat
    zamanlayici_baslat(app)

    return app

def ornek_veri_olustur(app):
    from .models import Kullanici, Masa
    import qrcode

    # Admin kullanıcı
    if not Kullanici.query.filter_by(ogrenci_no='admin').first():
        from app import bcrypt
        admin = Kullanici(
            ogrenci_no='admin',
            ad_soyad='Kütüphane Yöneticisi',
            email='admin@ege.edu.tr',
            sifre_hash=bcrypt.generate_password_hash('admin123').decode('utf-8'),
            rol='admin'
        )
        db.session.add(admin)

    # Demo öğrenci
    if not Kullanici.query.filter_by(ogrenci_no='45230000535').first():
        from app import bcrypt
        ogrenci = Kullanici(
            ogrenci_no='45230000535',
            ad_soyad='Eren Doğan',
            email='eren@ege.edu.tr',
            sifre_hash=bcrypt.generate_password_hash('eren123').decode('utf-8'),
            rol='ogrenci'
        )
        db.session.add(ogrenci)

    # Masalar — kat bazlı
    if Masa.query.count() == 0:
        # Kat 1: Sessiz Çalışma Alanı
        # Kat 2: Bireysel Çalışma Alanı
        # Kat 3: Grup Çalışma Alanı
        kat_verileri = {
            1: [
                ('Sessiz Çalışma', 'sessiz',
                 ['K1-S01','K1-S02','K1-S03','K1-S04','K1-S05',
                  'K1-S06','K1-S07','K1-S08','K1-S09','K1-S10']),
            ],
            2: [
                ('Bireysel Çalışma', 'bireysel',
                 ['K2-B01','K2-B02','K2-B03','K2-B04',
                  'K2-B05','K2-B06','K2-B07','K2-B08']),
            ],
            3: [
                ('Grup Çalışma', 'grup',
                 ['K3-G01','K3-G02','K3-G03','K3-G04','K3-G05','K3-G06']),
                ('Sessiz Çalışma', 'sessiz',
                 ['K3-S01','K3-S02','K3-S03','K3-S04']),
            ],
        }

        qr_klasor = os.path.join(app.static_folder, 'qrcodes')
        os.makedirs(qr_klasor, exist_ok=True)

        for kat_no, bolgeler in kat_verileri.items():
            for bolge_adi, bolge_turu, kodlar in bolgeler:
                for kod in kodlar:
                    qr_yolu = os.path.join(qr_klasor, f'{kod}.png')
                    qr = qrcode.QRCode(version=1, box_size=8, border=2)
                    qr.add_data(f'http://192.168.111.3:5001/masa/{kod}')
                    qr.make(fit=True)
                    img = qr.make_image(fill_color='black', back_color='white')
                    img.save(qr_yolu)

                    masa = Masa(
                        masa_kodu=kod,
                        kat=kat_no,
                        bolge=bolge_adi,
                        bolge_turu=bolge_turu,
                        durum='bos',
                        qr_resim_yolu=f'qrcodes/{kod}.png',
                        bluetooth_isim=f'KUT-{kod}'   # Masaya yapıştırılan BLE beacon adı
                    )
                    db.session.add(masa)

    db.session.commit()
