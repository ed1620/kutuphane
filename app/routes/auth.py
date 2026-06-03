from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from ..models import db, Kullanici
from app import bcrypt

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/giris', methods=['GET', 'POST'])
def giris():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        ogrenci_no = request.form.get('ogrenci_no', '').strip()
        sifre      = request.form.get('sifre', '')

        kullanici = Kullanici.query.filter_by(ogrenci_no=ogrenci_no).first()
        if kullanici and bcrypt.check_password_hash(kullanici.sifre_hash, sifre):
            login_user(kullanici)
            flash(f'Hoşgeldiniz, {kullanici.ad_soyad}!', 'success')
            sonraki = request.args.get('next')
            return redirect(sonraki or url_for('main.dashboard'))
        else:
            flash('Öğrenci numarası veya şifre hatalı.', 'danger')

    return render_template('giris.html')

@auth_bp.route('/kayit', methods=['GET', 'POST'])
def kayit():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        ogrenci_no = request.form.get('ogrenci_no', '').strip()
        ad_soyad   = request.form.get('ad_soyad', '').strip()
        email      = request.form.get('email', '').strip()
        sifre      = request.form.get('sifre', '')
        sifre2     = request.form.get('sifre2', '')

        if sifre != sifre2:
            flash('Şifreler eşleşmiyor.', 'danger')
            return render_template('kayit.html')

        if Kullanici.query.filter_by(ogrenci_no=ogrenci_no).first():
            flash('Bu öğrenci numarası zaten kayıtlı.', 'danger')
            return render_template('kayit.html')

        if Kullanici.query.filter_by(email=email).first():
            flash('Bu e-posta adresi zaten kullanımda.', 'danger')
            return render_template('kayit.html')

        sifre_hash = bcrypt.generate_password_hash(sifre).decode('utf-8')
        kullanici  = Kullanici(
            ogrenci_no=ogrenci_no,
            ad_soyad=ad_soyad,
            email=email,
            sifre_hash=sifre_hash
        )
        db.session.add(kullanici)
        db.session.commit()
        flash('Kayıt başarılı! Giriş yapabilirsiniz.', 'success')
        return redirect(url_for('auth.giris'))

    return render_template('kayit.html')

@auth_bp.route('/cikis')
@login_required
def cikis():
    logout_user()
    flash('Çıkış yapıldı.', 'info')
    return redirect(url_for('auth.giris'))


@auth_bp.route('/ege-sso')
def ege_sso():
    """Ege Üniversitesi kimlik sistemi ile SSO girişi.

    Gerçek entegrasyon için üniversite BT biriminden OAuth2 client_id/secret alınması gerekir.
    Şu an kimlik.ege.edu.tr giriş sayfasına yönlendirir.
    """
    import os
    # Gelecekte: OAuth2/OIDC entegrasyonu için client_id gerekli
    # client_id = os.environ.get('EGE_OAUTH_CLIENT_ID')
    # Şimdilik doğrudan yönlendir
    flash('Ege Kimlik Sistemi entegrasyonu için üniversite BT birimi ile iletişime geçin. Lütfen normal giriş yapın.', 'info')
    return redirect('https://kimlik.ege.edu.tr/Identity/Account/Login')
