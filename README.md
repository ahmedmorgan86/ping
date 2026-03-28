# Ping App - Railway Deployment

## المشاكل اللي تم إصلاحها:
1. `server.js` كان يستخدم ES Modules (`import`) لكن `package.json` مضبوط على CommonJS → تم التحويل لـ `require()`
2. أُضيف `"start"` script في `package.json` (مطلوب لـ Railway)
3. Express رُجّع لنسخة `4.x` (أكثر استقراراً من `5.x`)
4. أُضيف `"engines"` field لتحديد إصدار Node.js
5. أُنشئ `dist/index.html` (كان مفقوداً)
6. أُضيف `railway.json` لإعدادات الـ deployment
7. أُضيف `.gitignore`

## خطوات الـ Deploy على Railway:

1. ارفع الملفات على GitHub repo جديد
2. ادخل على [railway.app](https://railway.app)
3. اختر "New Project" → "Deploy from GitHub repo"
4. اختر الـ repo واضغط Deploy
5. Railway هيشتغل تلقائياً ويعطيك URL

## تشغيل محلياً:
```bash
npm install
npm start
```
