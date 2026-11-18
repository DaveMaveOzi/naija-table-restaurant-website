Naija Table – Admin icon font correction

Fixes Streamlit icon ligatures displaying as raw words such as 'arrow_right' and 'visibility'. The global Poppins typography rule had overridden Streamlit's icon font. The update restores the Material Symbols/Material Icons font for Streamlit icon elements while keeping Poppins for normal text.

Replace app.py. Keep your existing restaurant.db, uploads folder, and .streamlit/secrets.toml.
Restart locally with: streamlit run app.py
