"""
Streamlit app: Simple Amazon-style scraper demo (single file).
Features:
- Input product keyword
- Scrape search result pages (basic, polite)
- Preview scraped table
- Download CSV / Excel
- Basic analytics: counts, rating distribution, price distribution, scatter price vs rating

USAGE:
    streamlit run streamlit_amazon_scraper.py

WARNING: polite scraping only. Respect site's terms and set low num_pages/delay.
"""
from typing import List, Dict, Optional, Tuple
import time
import io
import math
import logging

import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import streamlit as st

# ---------------------- Config / Headers ----------------------
HEADERS = {
    "Referer": "https://www.amazon.com/",
    "Sec-Ch-Ua": "Not_A Brand",
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": "macOS",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"
}

# ---------------------- Helper functions ----------------------
def safe_text(elem) -> Optional[str]:
    if elem is None:
        return None
    return elem.get_text(strip=True)

def parse_price(price_text: Optional[str]) -> Optional[float]:
    """Try to convert price string like '$12.34' or 'USD 12.34' to float."""
    if not price_text:
        return None
    # remove common currency symbols/labels
    cleaned = price_text.replace(',', '').replace('USD', '').replace('US$', '')
    # keep digits and dot and minus
    chars = []
    for ch in cleaned:
        if ch.isdigit() or ch == '.':
            chars.append(ch)
    s = ''.join(chars)
    try:
        return float(s) if s else None
    except:
        return None

def parse_rating(rating_text: Optional[str]) -> Optional[float]:
    """Parse rating like '4.5 out of 5 stars' -> 4.5"""
    if not rating_text:
        return None
    parts = rating_text.strip().split()
    for token in parts:
        try:
            val = float(token)
            return val
        except:
            continue
    return None

def find_product_blocks(soup: BeautifulSoup) -> List[BeautifulSoup]:
    """
    Try a few common selectors for Amazon-like search results.
    """
    # Prefer the stable 'data-component-type="s-search-result"'
    blocks = soup.find_all("div", {"data-component-type": "s-search-result"})
    if blocks:
        return blocks
    # fallback to other known container classes (less reliable)
    blocks = soup.find_all("div", {"class": "a-section a-spacing-medium"})
    if blocks:
        return blocks
    # final fallback: any 'div' with 'data-asin' attribute
    blocks = [d for d in soup.find_all("div") if d.get("data-asin")]
    return blocks

def extract_from_block(block) -> Dict:
    """Extract title, link, price, rating, author/seller if possible from a result block."""
    # Title
    title = None
    title_h2 = block.find("h2")
    if title_h2:
        span = title_h2.find("span")
        title = safe_text(span) or safe_text(title_h2)

    # Alternative title selectors
    if not title:
        a_title = block.find("a", {"class": "a-link-normal a-text-normal"})
        title = safe_text(a_title) or title

    # Link / asin
    link = None
    a_tag = block.find("a", href=True)
    if a_tag:
        link = "https://www.amazon.com" + a_tag["href"]

    # Price
    price = None
    # common Amazon price elements
    price_span = block.find("span", {"class": "a-price"})
    if price_span:
        price_offscreen = price_span.find("span", {"class": "a-offscreen"})
        price = safe_text(price_offscreen)
    if not price:
        # fallback
        price = safe_text(block.find("span", {"class": "a-color-base"}))

    # Rating
    rating_text = None
    rating_span = block.find("span", {"class": "a-icon-alt"})
    if rating_span:
        rating_text = safe_text(rating_span)
    else:
        # fallback: check for aria-label with rating
        aria = block.find(attrs={"aria-label": True})
        if aria and "out of 5 stars" in aria["aria-label"]:
            rating_text = aria["aria-label"]

    # Author / seller (books often have author in this area)
    author = None
    # Try common book author container
    author_container = block.find("div", {"class": "a-row a-size-base a-color-secondary"})
    if author_container:
        a_auth = author_container.find("a")
        author = safe_text(a_auth) or safe_text(author_container)
    # fallback: look for byline
    if not author:
        byline = block.find("span", string=lambda s: s and "by " in s.lower())
        if byline:
            author = safe_text(byline)

    # Return structured dict
    return {
        "title": title,
        "link": link,
        "price_raw": price,
        "price": parse_price(price),
        "rating_raw": rating_text,
        "rating": parse_rating(rating_text),
        "author": author,
    }

# ---------------------- Scraper core ----------------------
def scrape_amazon_search(keyword: str, max_pages: int = 2, sleep_sec: float = 1.0, max_items: Optional[int] = None, logger: Optional[logging.Logger]=None) -> List[Dict]:
    """
    Scrape Amazon search result pages for `keyword`.
    - max_pages: how many result pages to crawl (keep small e.g., 1-3)
    - sleep_sec: delay between page requests (politeness)
    - max_items: optional cap on total items to collect
    Returns list of product dicts.
    """
    if logger is None:
        logger = logging.getLogger("scraper")
    items = []
    seen = set()
    base_query = keyword.strip().replace(" ", "+")
    page = 1
    while page <= max_pages:
        url = f"https://www.amazon.com/s?k={base_query}&page={page}"
        logger.info(f"Requesting {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            break

        logger.info(f"Status: {resp.status_code}")
        if resp.status_code != 200:
            logger.error(f"Non-200 status code: {resp.status_code}. Stopping.")
            break

        soup = BeautifulSoup(resp.content, "html.parser")
        blocks = find_product_blocks(soup)
        logger.info(f"Found {len(blocks)} blocks on page {page}")

        found_this_page = 0
        for b in blocks:
            data = extract_from_block(b)
            if not data.get("title"):
                continue
            title = data["title"]
            if title in seen:
                continue
            seen.add(title)
            items.append(data)
            found_this_page += 1
            if max_items and len(items) >= max_items:
                break
        logger.info(f"Added {found_this_page} new items from page {page} (total={len(items)})")
        # politeness
        time.sleep(sleep_sec)
        if max_items and len(items) >= max_items:
            break
        # break early if no results
        if found_this_page == 0:
            break
        page += 1
    return items

# ---------------------- Streamlit UI ----------------------
st.set_page_config(page_title="Amazon-style Scraper (Demo)", layout="wide")
st.title("Amazon-style Scraper — Demo")
st.markdown(
    "Masukkan kata kunci produk, atur jumlah halaman dan jeda (polite scraping). "
    "**Hanya untuk demo/pendidikan** — gunakan dengan etika dan patuhi Terms."
)

# Sidebar controls
with st.sidebar:
    st.header("Controls")
    keyword = st.text_input("Product keyword", value="data science books")
    max_pages = st.slider("Max pages to crawl", min_value=1, max_value=5, value=2)
    max_items = st.number_input("Max items (0 = unlimited)", min_value=0, max_value=500, value=0)
    delay = st.slider("Delay between requests (sec)", min_value=0.5, max_value=5.0, value=1.0, step=0.5)
    run_btn = st.button("Start scraping")
    st.markdown("---")
    st.markdown("Notes:\n- Keep pages small (1-3) and delay >= 1s for politeness.\n- Results depend on site's HTML (may break if site changes).")

# Run scraper when button clicked
if run_btn and keyword.strip():
    placeholder = st.empty()
    status = st.empty()
    logger = logging.getLogger("scraper")
    logger.setLevel(logging.INFO)

    # show simple progress UI
    with st.spinner("Scraping... this may take a few seconds per page"):
        try:
            items = scrape_amazon_search(
                keyword=keyword,
                max_pages=max_pages,
                sleep_sec=delay,
                max_items=(None if max_items == 0 else int(max_items)),
                logger=logger
            )
        except Exception as e:
            st.error(f"Scraper error: {e}")
            items = []

    if not items:
        st.warning("No items collected. Mungkin struktur halaman berubah atau tidak ada hasil.")
    else:
        df = pd.DataFrame(items)
        # standardize columns
        df = df[["title", "author", "price_raw", "price", "rating_raw", "rating", "link"]]
        df = df.rename(columns={
            "title": "Title",
            "author": "Author",
            "price_raw": "Price (raw)",
            "price": "Price",
            "rating_raw": "Rating (raw)",
            "rating": "Rating",
            "link": "Link"
        })

        st.subheader("Preview scraped data")
        st.dataframe(df, use_container_width=True)

        # Download buttons
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv_bytes, file_name="scraped_products.csv", mime="text/csv")

        # Excel
        towrite = io.BytesIO()
        with pd.ExcelWriter(towrite, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="scraped")
        towrite.seek(0)

        st.download_button(
            "Download Excel (.xlsx)",
            towrite.read(),
            file_name="scraped_products.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        # ---------------- Analytics ----------------
        st.subheader("Statistics & Trends")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total items", f"{len(df)}")
            n_with_price = df["Price"].count()
            st.metric("Items with parsed price", f"{n_with_price} ({n_with_price/len(df)*100:.1f}%)")
        with col2:
            n_with_rating = df["Rating"].count()
            st.metric("Items with rating", f"{n_with_rating} ({n_with_rating/len(df)*100:.1f}%)")
        with col3:
            avg_price = df["Price"].dropna().mean()
            st.metric("Average price (parsed)", f"{avg_price:.2f}" if not math.isnan(avg_price) else "N/A")

        # Price distribution
        st.markdown("**Price distribution (parsed)**")
        price_df = df[["Title", "Price"]].dropna()
        if not price_df.empty:
            st.bar_chart(price_df["Price"].astype(float).round(2).value_counts().sort_index())
            st.line_chart(price_df["Price"].astype(float).reset_index(drop=True))
        else:
            st.info("Tidak ada data harga yang berhasil diparsing.")

        # Rating distribution
        st.markdown("**Rating distribution**")
        rating_df = df[["Title", "Rating"]].dropna()
        if not rating_df.empty:
            st.bar_chart(rating_df["Rating"].value_counts().sort_index())
        else:
            st.info("Tidak ada data rating yang berhasil diparsing.")

        # Scatter price vs rating
        st.markdown("**Price vs Rating (scatter)**")
        scatter_df = df.dropna(subset=["Price", "Rating"])
        if not scatter_df.empty:
            st.altair_chart(
                __import__("altair").Chart(scatter_df).mark_circle(size=60).encode(
                    x="Price",
                    y="Rating",
                    tooltip=["Title", "Author", "Price", "Rating"]
                ).interactive().properties(height=400),
                use_container_width=True
            )
        else:
            st.info("Butuh minimal satu item dengan price & rating untuk scatter plot.")

        # Top authors
        st.markdown("**Top authors / sellers (by count)**")
        if "Author" in df.columns and df["Author"].notna().any():
            top_auth = df["Author"].fillna("Unknown").value_counts().head(10)
            st.table(top_auth.reset_index().rename(columns={"index": "Author", "Author": "Count"}))
        else:
            st.info("Tidak ada informasi author yang berhasil diekstrak.")

        st.success("Selesai — ingat untuk menggunakan scraper ini dengan etika.")
else:
    st.info("Masukkan keyword dan tekan *Start scraping* untuk memulai (demo: 'data science books').")
