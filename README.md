# Naija Table – Responsive Header Update

## Run locally

1. Open this folder in PyCharm.
2. Activate your existing virtual environment.
3. Install dependencies if needed:
   `pip install -r requirements.txt`
4. Keep your existing `restaurant.db`, `uploads/`, and `.streamlit/secrets.toml` when replacing the application in an existing project.
5. Start the app:
   `streamlit run app.py`

## Header changes

- Desktop, laptop and tablet use a dedicated desktop header: brand on the left and theme toggle at the far right. No hamburger menu is rendered in this layout.
- Mobile uses a separate header: brand on its own first row, then hamburger and theme toggle on a second row below it.
- Mobile navigation closes after a navigation option is selected.

Do not commit `.streamlit/secrets.toml` or real credentials to GitHub.
