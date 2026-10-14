import streamlit as st
import streamlit.components.v1 as components

# Streamlit-Konfiguration für die volle Breite
st.set_page_config(page_title="Wehringer Steelers - Team", layout="wide")

# Vollständiger HTML- und CSS-Code für die Deprecation-Notice
html_code = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <style>
        body { 
          background-color: #0e1117; 
          color: white; 
          font-family: sans-serif; 
          margin: 0; 
          padding: 0; 
          overflow-x: hidden;
        }
        .app-container { 
          position: relative; 
          width: 100%; 
          min-height: 100vh;
          margin: 0; 
          padding: 10px; 
          box-sizing: border-box;
          display: flex;
          flex-direction: column;
        }
        .header-hero { 
          position: relative;
          width: 100%;
          min-height: 110px;
          background: linear-gradient(135deg, #161b22 0%, #0e1117 100%);
          border-radius: 12px;
          border: 1px solid #444;
          margin-bottom: 20px;
          box-shadow: 0 6px 16px rgba(0,0,0,0.6);
          display: flex;
          align-items: center;
          padding: 15px 25px;
          box-sizing: border-box;
          overflow: hidden;
        }
        .hero-content {
          position: relative;
          z-index: 2;
          display: flex;
          align-items: center;
          gap: 20px;
          width: 100%;
        }
        .header-logo {
          height: 75px;
          width: auto;
          object-fit: contain;
          filter: drop-shadow(0 4px 8px rgba(0,0,0,0.6));
          border-radius: 6px;
          flex-shrink: 0;
        }
        .logo-text-group {
          display: flex;
          flex-direction: column;
          justify-content: center;
        }
        .logo-text-group h1 { 
          margin: 0; 
          color: #fff; 
          font-size: 2.1rem; 
          font-weight: 900;
          letter-spacing: 0.8px;
          text-shadow: 2px 2px 6px rgba(0,0,0,0.8);
          white-space: nowrap;
        }
        .subtitle { 
          margin: 4px 0 0 0; 
          color: #4CAF50; 
          font-weight: bold; 
          font-size: 1rem; 
          text-shadow: 1px 1px 3px rgba(0,0,0,0.8);
        }
        .tabs { 
          display: flex; 
          gap: 8px; 
          background: #1e1e1e; 
          padding: 8px; 
          border-radius: 8px; 
          margin-bottom: 15px; 
        }
        .tab-btn { 
          background: #4CAF50; 
          color: white; 
          border: none; 
          padding: 8px 14px; 
          font-size: 0.95rem; 
          border-radius: 6px; 
          font-weight: bold; 
        }
        .content { 
          background: #1e1e1e; 
          padding: 30px; 
          border-radius: 8px; 
          flex: 1;
          border: 1px solid #333; 
          box-shadow: 0 4px 6px rgba(0,0,0,0.3); 
          box-sizing: border-box;
          text-align: center;
          display: flex;
          flex-direction: column;
          justify-content: center;
          align-items: center;
          min-height: 400px;
        }
        .update-banner {
          max-width: 600px;
          padding: 20px;
        }
        .update-banner h2 {
          color: #ff9800;
          margin-top: 0;
          font-size: 1.8rem;
        }
        .update-banner p {
          color: #ccc;
          font-size: 1.1rem;
          line-height: 1.5;
        }
        .btn-goto-new {
          display: inline-block;
          background: #4CAF50;
          color: white;
          text-decoration: none;
          padding: 14px 28px;
          border-radius: 8px;
          font-size: 1.2rem;
          font-weight: bold;
          box-shadow: 0 4px 10px rgba(76, 175, 80, 0.4);
          transition: 0.2s;
        }
        .btn-goto-new:hover {
          background: #388e3c;
          transform: translateY(-2px);
        }
    </style>
</head>
<body>
<div class="app-container">

    <header class="header-hero">
      <div class="hero-content">
        <!-- Hinweis: Stelle sicher, dass header.png im selben Ordner oder im static-Pfad von Streamlit liegt -->
        <img src="https://raw.githubusercontent.com/" alt="Steelers Logo" class="header-logo" onerror="this.style.display='none'" />
        <div class="logo-text-group">
          <h1>Wehringer Steelers - Team</h1>
          <p class="subtitle">Alles rund um die Mannschaft</p>
        </div>
      </div>
    </header>

    <nav class="tabs">
      <button class="tab-btn active">
        &#127968; Übersicht
      </button>
    </nav>

    <main class="content">
      <div class="update-banner">
        <h2>&#128640; Es gibt eine neue Version der App!</h2>
        <p>Diese alte Version wird nicht mehr aktiv verwendet. Bitte wechsle auf unsere neue, verbesserte Plattform.</p>
        <br>
        <a href="https://steelers-app-94e32.web.app/" target="_blank" class="btn-goto-new">
          &#128279; Zur neuen Steelers-App wechseln
        </a>
      </div>
    </main>

</div>
</body>
</html>
"""

# Rendert das HTML/CSS direkt als echte Webseite in Streamlit
components.html(html_code, height=650, scrolling=True)
