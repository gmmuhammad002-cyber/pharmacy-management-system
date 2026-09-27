# Eczane Yönetim Sistemi

Flask tabanlı eczane yönetim sistemi.

## GitHub

Bu klasörü GitHub repository'sinin kök dizinine yükleyin.

**GitHub'a yüklemeyin:**
- `.env`
- `*.db`
- `__pycache__/`

`.env.example` yalnızca örnek değişkenleri gösterir.

## Render

Projede `render.yaml` hazırdır. Render'da **New + Blueprint** seçip GitHub repository'sini bağlayabilirsiniz.

Render şu bileşenleri oluşturacak şekilde tanımlanmıştır:
- Flask web service
- PostgreSQL database
- `SECRET_KEY` otomatik üretimi
- `DATABASE_URL` PostgreSQL bağlantısı
- İlk admin parolası için `INITIAL_ADMIN_PASSWORD`

`INITIAL_ADMIN_PASSWORD` değerini Render deploy ekranında güçlü bir parola olarak girin.

### Manuel Render ayarları

Eğer Blueprint kullanmazsanız:

**Build Command**
```bash
pip install -r requirements.txt
```

**Start Command**
```bash
gunicorn app:app
```

Gerekli Environment Variables:
- `SECRET_KEY`
- `DATABASE_URL`
- `INITIAL_ADMIN_PASSWORD`

`DATABASE_URL`, Render PostgreSQL servisinin internal connection string değeridir.

## Yerel çalıştırma

```bash
pip install -r requirements.txt
```

Sonra `.env.example` dosyasını `.env` olarak kopyalayıp değerleri düzenleyin.

```bash
python app.py
```

Varsayılan geliştirme adresi:
`http://127.0.0.1:5000`

## İlk giriş

Admin kullanıcı adı:
`admin`

Admin parolası:
`INITIAL_ADMIN_PASSWORD` environment variable değeri.

Production ortamında varsayılan `admin123` parolasını kullanmayın.
