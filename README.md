# Amazon Web Scraper

This project is a simple **Streamlit web app** that scrapes products data from **Amazon** based on any keyword entered by the user.
It displays the results in a table, provides downloadable files (CSV/Excel), and shows basic statistics and visualizations about the products.

## Features

* **Keyword Search**: Enter any product keyword (e.g., *"data science books"*, *"gaming laptop"*, etc.)
* **Preview Table**: Display scraped product details (title, author/seller, price, rating).
* **Export Results**: Download data as **CSV** or **Excel**.
* **Product Insights**:

  * Distribution of product ratings
  * Price statistics (min, max, average)
  * Scatter plot of **Price vs Rating** to detect trends

## How to Use

1. **Clone the Repository**

   ```bash
   git clone https://github.com/your-username/amazon-scraper-streamlit.git
   cd amazon-scraper-streamlit
   ```

2. **Install Dependencies**
   Using the provided `requirements.txt`:

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the App Locally**

   ```bash
   streamlit run app.py
   ```

4. **Open in Browser**
   The app will automatically open at:
   👉 [http://localhost:8501](http://localhost:8501)

5. **Scraping Workflow**

   * Enter a **product keyword** (e.g., "headphones")
   * Set the maximum number of pages
   * Click **Start scraping**
   * View results in an interactive table
   * Download as CSV/Excel
   * Explore charts and statistics about the products
  
## Screenshots
<p align="center">
  <img src="img/Screenshot%20(847).png" alt="847" width="250"/>
  <img src="img/Screenshot%20(848).png" alt="848" width="250"/>
  <img src="img/Screenshot%20(849).png" alt="849" width="250"/>
</p>

