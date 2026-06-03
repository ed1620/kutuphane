import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from io import BytesIO
import base64

def grafik_olustur(app):
    """Son 7 günün saatlik yoğunluk grafiğini base64 olarak döner."""
    with app.app_context():
        from .models import Rezervasyon

        simdi = datetime.utcnow()
        yedi_gun_once = simdi - timedelta(days=7)

        rezervasyonlar = Rezervasyon.query.filter(
            Rezervasyon.giris_zamani >= yedi_gun_once
        ).all()

        saat_sayilari = [0] * 24
        for r in rezervasyonlar:
            saat = r.giris_zamani.hour
            saat_sayilari[saat] += 1

        fig, ax = plt.subplots(figsize=(10, 4))
        fig.patch.set_facecolor('#1a1a2e')
        ax.set_facecolor('#16213e')

        saatler = list(range(24))
        renkler = ['#e94560' if s == max(saat_sayilari) else '#0f3460' for s in saat_sayilari]
        bars = ax.bar(saatler, saat_sayilari, color=renkler, edgecolor='#e94560', linewidth=0.5)

        ax.set_xlabel('Saat', color='white', fontsize=11)
        ax.set_ylabel('Rezervasyon Sayısı', color='white', fontsize=11)
        ax.set_title('Son 7 Günün Saatlik Yoğunluğu', color='white', fontsize=13, fontweight='bold')
        ax.tick_params(colors='white')
        ax.spines['bottom'].set_color('#e94560')
        ax.spines['left'].set_color('#e94560')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.set_xticks(saatler)
        ax.set_xticklabels([f'{s:02d}:00' for s in saatler], rotation=45, ha='right', fontsize=8, color='white')

        plt.tight_layout()

        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        grafik_b64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()

        return grafik_b64

def doluluk_istatistigi():
    """Anlık doluluk istatistiklerini döner."""
    from .models import Masa
    toplam = Masa.query.count()
    dolu   = Masa.query.filter_by(durum='dolu').count()
    molada = Masa.query.filter_by(durum='molada').count()
    bos    = Masa.query.filter_by(durum='bos').count()
    return {
        'toplam': toplam,
        'dolu': dolu,
        'molada': molada,
        'bos': bos,
        'doluluk_orani': round((dolu + molada) / toplam * 100, 1) if toplam > 0 else 0
    }
