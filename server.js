const express = require("express");

const app = express();
const PORT = process.env.PORT || 3000;

const html = `<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Ping App</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: Arial, sans-serif; display: flex; flex-direction: column; justify-content: center; align-items: center; min-height: 100vh; background: #f0f4f8; }
    .card { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); text-align: center; }
    h1 { color: #333; margin-bottom: 12px; }
    p { color: #666; margin-bottom: 16px; }
    .badge { background: #4CAF50; color: white; padding: 6px 16px; border-radius: 20px; font-size: 14px; }
    footer { margin-top: 24px; font-size: 13px; color: #999; }
  </style>
</head>
<body>
  <div class="card">
    <h1>🏓 Ping</h1>
    <p>التطبيق شغال بنجاح!</p>
    <span class="badge">✓ Online</span>
  </div>
  <footer>
    &copy; <span id="year"></span> Ahmed Morgan. All rights reserved.
  </footer>
  <script>
    document.getElementById("year").textContent = new Date().getFullYear();
  </script>
</body>
</html>`;

// Health check for Railway
app.get("/health", (req, res) => {
  res.status(200).json({ status: "ok" });
});

// Serve the app
app.get("*", (req, res) => {
  res.send(html);
});

app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
