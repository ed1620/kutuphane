from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta


def otomatik_tahliye(app):
    """Her dakika çalışır: süresi dolan rezervasyonları ve doğrulanmayanları iptal eder."""
    with app.app_context():
        from .models import db, Rezervasyon, Masa
        from config import Config

        simdi = datetime.utcnow()

        # 1) Süresi dolan aktif/molada rezervasyonları iptal et
        suresi_dolan = Rezervasyon.query.filter(
            Rezervasyon.durum.in_(['aktif', 'molada']),
            Rezervasyon.bitis_zamani <= simdi
        ).all()

        for rez in suresi_dolan:
            rez.durum = 'otomatik_iptal'
            rez.cikis_zamani = simdi
            masa = Masa.query.get(rez.masa_id)
            if masa:
                masa.durum = 'bos'

        if suresi_dolan:
            db.session.commit()
            print(f"[Scheduler] {len(suresi_dolan)} rezervasyon süresi dolduğu için iptal edildi.")

        # 2) Doğrulama bekleniyor ama süresi dolmuş olanları iptal et
        dogrulama_suresi_dolan = Rezervasyon.query.filter(
            Rezervasyon.durum == 'aktif',
            Rezervasyon.dogrulama_bekleniyor == True,
            Rezervasyon.dogrulama_bitis <= simdi
        ).all()

        for rez in dogrulama_suresi_dolan:
            rez.durum = 'otomatik_iptal'
            rez.cikis_zamani = simdi
            masa = Masa.query.get(rez.masa_id)
            if masa:
                masa.durum = 'bos'

        if dogrulama_suresi_dolan:
            db.session.commit()
            print(f"[Scheduler] {len(dogrulama_suresi_dolan)} rezervasyon QR doğrulaması yapılmadığı için iptal edildi.")


def dogrulama_iste(app):
    """Her 5 dakikada çalışır: doğrulama zamanı gelen rezervasyonlara doğrulama isteği gönderir."""
    with app.app_context():
        from .models import db, Rezervasyon
        from config import Config

        simdi = datetime.utcnow()
        aralik = timedelta(minutes=Config.DOGRULAMA_ARALIGI_DK)
        bekleme = timedelta(minutes=Config.DOGRULAMA_BEKLEME_DK)

        # Aktif, henüz doğrulama beklemediği ve son doğrulamanın üzerinden yeterli süre geçmiş rezervasyonlar
        dogrulama_gerekli = Rezervasyon.query.filter(
            Rezervasyon.durum == 'aktif',
            Rezervasyon.dogrulama_bekleniyor == False,
            Rezervasyon.son_dogrulama.isnot(None),
            Rezervasyon.son_dogrulama <= simdi - aralik
        ).all()

        for rez in dogrulama_gerekli:
            rez.dogrulama_bekleniyor = True
            rez.dogrulama_bitis = simdi + bekleme

        if dogrulama_gerekli:
            db.session.commit()
            print(f"[Scheduler] {len(dogrulama_gerekli)} rezervasyon için doğrulama istendi.")


def zamanlayici_baslat(app):
    scheduler = BackgroundScheduler()

    # Her dakika: tahliye ve doğrulanmayan masaları boşalt
    scheduler.add_job(
        func=otomatik_tahliye,
        args=[app],
        trigger='interval',
        minutes=1,
        id='tahliye_job'
    )

    # Her 5 dakika: doğrulama isteği gönder
    scheduler.add_job(
        func=dogrulama_iste,
        args=[app],
        trigger='interval',
        minutes=5,
        id='dogrulama_job'
    )

    scheduler.start()
    print("[Scheduler] Otomatik tahliye ve periyodik doğrulama algoritmaları başlatıldı.")
