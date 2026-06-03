import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'gizli-anahtar-degistir')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///kutuphane.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Mola süreleri (dakika)
    NORMAL_MOLA_DK = 15          # Normal mola süresi
    YEMEK_MOLA_DK  = 60          # Yemek molası süresi
    MIN_SURE_MOLA_DK = 30        # Mola almak için minimum oturma süresi

    # Periyodik doğrulama
    DOGRULAMA_ARALIGI_DK = 45    # Her X dakikada bir QR doğrulama istenir
    DOGRULAMA_BEKLEME_DK = 10    # Doğrulama için bekleme süresi (aksi halde masa boş)

    # Maksimum oturma süresi (dakika)
    MAX_OTURMA_SURESI_DK = 240   # 4 saat

    # Uyarı süresi
    UYARI_SURESI_DK = 10         # Süre dolmadan kaç dk önce uyarı

    # QR kod klasörü
    QR_KLASOR = os.path.join('static', 'qrcodes')
