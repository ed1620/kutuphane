from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class Kullanici(UserMixin, db.Model):
    __tablename__ = 'kullanici'
    id            = db.Column(db.Integer, primary_key=True)
    ogrenci_no    = db.Column(db.String(20), unique=True, nullable=False)
    ad_soyad      = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    sifre_hash    = db.Column(db.String(256), nullable=False)
    rol           = db.Column(db.String(10), default='ogrenci')  # 'ogrenci' | 'admin'
    olusturulma   = db.Column(db.DateTime, default=datetime.utcnow)
    rezervasyonlar = db.relationship('Rezervasyon', backref='kullanici', lazy=True)

    def __repr__(self):
        return f'<Kullanici {self.ogrenci_no}>'


class Masa(db.Model):
    __tablename__ = 'masa'
    id            = db.Column(db.Integer, primary_key=True)
    masa_kodu     = db.Column(db.String(20), unique=True, nullable=False)  # örn. "K1-A01"
    kat           = db.Column(db.Integer, default=1)                       # Kat numarası
    bolge         = db.Column(db.String(50))                               # örn. "Sessiz Çalışma"
    bolge_turu    = db.Column(db.String(20), default='sessiz')             # 'sessiz' | 'grup' | 'bireysel'
    durum         = db.Column(db.String(10), default='bos')                # 'bos' | 'dolu' | 'molada'
    qr_resim_yolu = db.Column(db.String(200))
    bluetooth_isim = db.Column(db.String(50))                              # BLE beacon adı, örn. "KUT-K1-S01"
    guncelleme    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    rezervasyonlar = db.relationship('Rezervasyon', backref='masa', lazy=True)

    def __repr__(self):
        return f'<Masa {self.masa_kodu}>'


class Rezervasyon(db.Model):
    __tablename__ = 'rezervasyon'
    id                    = db.Column(db.Integer, primary_key=True)
    kullanici_id          = db.Column(db.Integer, db.ForeignKey('kullanici.id'), nullable=False)
    masa_id               = db.Column(db.Integer, db.ForeignKey('masa.id'), nullable=False)
    giris_zamani          = db.Column(db.DateTime, default=datetime.utcnow)
    bitis_zamani          = db.Column(db.DateTime, nullable=False)
    cikis_zamani          = db.Column(db.DateTime)
    durum                 = db.Column(db.String(15), default='aktif')
    # 'aktif' | 'molada' | 'tamamlandi' | 'iptal' | 'otomatik_iptal'

    # Mola bilgileri
    mola_turu             = db.Column(db.String(10))   # 'normal' | 'yemek' | None
    mola_baslangic        = db.Column(db.DateTime)     # Molanın başladığı zaman

    # Periyodik doğrulama
    son_dogrulama         = db.Column(db.DateTime)     # Son doğrulama zamanı
    dogrulama_bekleniyor  = db.Column(db.Boolean, default=False)
    dogrulama_bitis       = db.Column(db.DateTime)     # Doğrulama için son tarih

    bildirimler = db.relationship('Bildirim', backref='rezervasyon', lazy=True)

    def __repr__(self):
        return f'<Rezervasyon {self.id} - Masa {self.masa_id}>'


class Bildirim(db.Model):
    __tablename__ = 'bildirim'
    id             = db.Column(db.Integer, primary_key=True)
    rezervasyon_id = db.Column(db.Integer, db.ForeignKey('rezervasyon.id'), nullable=False)
    tur            = db.Column(db.String(30))   # 'sure_uyarisi' | 'tahliye' | 'onay' | 'dogrulama_istegi'
    gonderim_zamani = db.Column(db.DateTime, default=datetime.utcnow)
    gonderildi     = db.Column(db.Boolean, default=False)
