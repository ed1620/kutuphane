from app import uygulama_olustur

app = uygulama_olustur()

if __name__ == '__main__':
    print("=" * 60)
    print("  EGE KÜTÜPHANESİ REZERVASYON SİSTEMİ")
    print("  http://localhost:5000")
    print()
    print("  Admin:  admin / admin123")
    print("  Demo:   45230000535 / eren123")
    print()
    print("  Özellikler:")
    print("  • 3 Katlı masa haritası (kat sekmeleri)")
    print("  • QR kod ile check-in / moladan dönüş")
    print("  • Normal mola (15 dk) | Yemek molası (60 dk)")
    print("  • 30 dk bekleme kuralı (mola öncesi)")
    print("  • Periyodik QR / Bluetooth varlık doğrulama")
    print("  • Doğrulama yapılmazsa masa otomatik boşaltılır")
    print("=" * 60)
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5001)
