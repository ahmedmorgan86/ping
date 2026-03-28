const express = require("express");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;

// Health check endpoint for Railway
app.get("/health", (req, res) => {
  res.status(200).json({ status: "ok" });
});

// Serve static files from dist
app.use(express.static(path.join(__dirname, "dist")));

// Catch-all: serve index.html for SPA routing (all unknown routes)
app.use((req, res) => {
  res.sendFile(path.join(__dirname, "dist", "index.html"));
});

app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
