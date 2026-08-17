-- ============================================================
-- Shuddh Swad — Business Data Store
-- Source: https://shuddhswad.shop/
-- Purpose: Raw structured data store for a future AI Agent
--          (customer support / sales / product-info agent)
-- Note: Prices/ratings/stock captured on scrape date; refresh
--       periodically as they change on the live store.
-- Scrape date: 2026-08-11
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- 1. Company / Brand Info
-- ------------------------------------------------------------
DROP TABLE IF EXISTS company_info;
CREATE TABLE company_info (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_name      TEXT NOT NULL,
    tagline         TEXT,
    description     TEXT,
    website_url     TEXT,
    founded_story   TEXT,
    address         TEXT,
    phone           TEXT,
    whatsapp_number TEXT,
    whatsapp_link   TEXT,
    email           TEXT,
    support_hours   TEXT,
    instagram_url   TEXT,
    youtube_url     TEXT,
    facebook_url    TEXT
);

INSERT INTO company_info (
    brand_name, tagline, description, website_url, founded_story,
    address, phone, whatsapp_number, whatsapp_link, email,
    support_hours, instagram_url, youtube_url, facebook_url
) VALUES (
    'Shuddh Swad',
    'Pure · Authentic · Traditional',
    'Authentic, pure Bihari/Jharkhand snacks (Thekua) delivered to your doorstep. No added preservatives, prepared fresh in hygienic conditions.',
    'https://shuddhswad.shop',
    'Founded by two teenagers from Bihar; started with roughly ₹10,000 home recipe capital and grew into a ~₹1 crore business, featured in NDTV, Economic Times, News18, DNA India, Moneymint, Latestly, Snackfax, Inshorts, Mathrubhumi, and The Better India.',
    'Adra, Near DVC More, West Bengal 723121, India',
    '+91 8016380734',
    '+91 8016380734',
    'https://wa.me/918016380734',
    'contact@shuddhswad.shop',
    'Mon–Fri, 10:00 AM to 6:30 PM',
    'https://www.instagram.com/shuddhswad49',
    'https://www.youtube.com/@ShuddhSwad49',
    'https://www.facebook.com/shuddhswad48/'
);

-- ------------------------------------------------------------
-- 2. Products
-- ------------------------------------------------------------
DROP TABLE IF EXISTS products;
CREATE TABLE products (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    slug                TEXT UNIQUE NOT NULL,
    url                 TEXT,
    category            TEXT,
    description         TEXT,
    shelf_life_days     INTEGER,
    storage_instructions TEXT,
    shipping_info       TEXT,
    preservatives       TEXT,
    rating              REAL,
    rating_count        INTEGER,
    units_sold          INTEGER,
    review_count        INTEGER,
    base_price_inr      REAL,
    mrp_inr             REAL,
    discount_pct        INTEGER,
    primary_image_url   TEXT
);

INSERT INTO products (
    name, slug, url, category, description, shelf_life_days,
    storage_instructions, shipping_info, preservatives,
    rating, rating_count, units_sold, review_count,
    base_price_inr, mrp_inr, discount_pct, primary_image_url
) VALUES
(
    'Shuddh Swad Traditional Thekua',
    'traditional-thekua',
    'https://shuddhswad.shop/products/traditional-thekua',
    'Thekua / Bihari Snack',
    'Traditional Thekua is a cherished snack from Bihar and Jharkhand, known as the "prasad of Chhath Puja." Made with whole wheat flour, jaggery/coconut-suji and ghee, deep-fried to a golden crisp. No added preservatives, prepared fresh in hygienic conditions.',
    90,
    'Store in a cool, dry place in an airtight container to retain freshness.',
    'Door delivery across India',
    'No added preservatives',
    4.8, 12847, 5420, 2284,
    299.00, 599.00, 50,
    'https://shuddhswad.shop/cdn/shop/files/Coconut_Suji_Thekua_Front_1.jpg?v=1782161158'
),
(
    'Shuddh Swad Jaggery Thekua',
    'jaggery-thekua',
    'https://shuddhswad.shop/products/jaggery-thekua',
    'Thekua / Bihari Snack',
    'Jaggery Thekua, prepared with whole wheat flour, pure jaggery, and ghee. Sacred offering during Chhath Puja; rich comforting jaggery flavor with a crispy bite. No added preservatives, prepared fresh in hygienic conditions.',
    90,
    'Store in a cool, dry place in an airtight container to retain freshness.',
    'Door delivery across India',
    'No added preservatives',
    4.8, 12847, 5420, 2284,
    299.00, 599.00, 50,
    'https://shuddhswad.shop/cdn/shop/files/Coconut_Jaggery_Thekua_Front_1.jpg?v=1782161149'
),
(
    'Shuddh Swad Elaichi Thekua',
    'elachi-thekua',
    'https://shuddhswad.shop/products/elachi-thekua',
    'Thekua / Bihari Snack',
    'Elaichi (cardamom) Thekua — authentic delicacy from Bihar and Jharkhand, popularly known as the "Prasad of Chhath Puja." Homepage summary only; full product page (price/variant detail) not fetched due to rate limiting — verify on next refresh.',
    NULL,
    'Store in a cool, dry place in an airtight container to retain freshness.',
    'Door delivery across India',
    'No added preservatives',
    NULL, NULL, NULL, NULL,
    299.00, 599.00, 50,
    'https://shuddhswad.shop/cdn/shop/files/Copy_of_Coconut_Elaichi_Thekua_Front.png?v=1782879951'
);

-- ------------------------------------------------------------
-- 3. Product Variants (Pack sizes / pricing)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS product_variants;
CREATE TABLE product_variants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL REFERENCES products(id),
    variant_label   TEXT NOT NULL,   -- e.g. '1 Pack (250g)'
    weight_grams    INTEGER,
    price_inr       REAL,
    savings_inr     REAL,
    is_best_seller  BOOLEAN DEFAULT 0,
    availability    TEXT              -- e.g. 'sold out', 'available' (unknown = not confirmed)
);

INSERT INTO product_variants (product_id, variant_label, weight_grams, price_inr, savings_inr, is_best_seller, availability) VALUES
-- Traditional Thekua (product_id = 1)
(1, '1 Pack (250g)', 250, 299.00, 300.00, 1, 'sold out / unavailable at scrape time'),
(1, '3 Pack (750g)', 750, 799.00, 1000.00, 0, 'sold out / unavailable at scrape time'),
(1, '5 Pack (1250g)', 1250, 1299.00, 1700.00, 0, 'sold out / unavailable at scrape time'),
-- Jaggery Thekua (product_id = 2)
(2, '1 pack 250g', 250, 299.00, 300.00, 1, 'sold out / unavailable at scrape time'),
(2, '3 pack 750g', 750, 799.00, 1000.00, 0, 'sold out / unavailable at scrape time'),
(2, '5 pack 1250g', 1250, 1299.00, 1700.00, 0, 'sold out / unavailable at scrape time'),
-- Elaichi Thekua (product_id = 3) - variant pricing not confirmed (page fetch failed, using homepage pattern)
(3, '1 pack 250g', 250, 299.00, 300.00, 1, 'unconfirmed - verify on refresh'),
(3, '3 pack 750g', 750, NULL, NULL, 0, 'unconfirmed - verify on refresh'),
(3, '5 pack 1250g', 1250, NULL, NULL, 0, 'unconfirmed - verify on refresh');

-- ------------------------------------------------------------
-- 4. Sample Product Reviews (as shown on site)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS product_reviews;
CREATE TABLE product_reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL REFERENCES products(id),
    reviewer_name   TEXT,
    star_rating     INTEGER,
    review_text     TEXT
);

INSERT INTO product_reviews (product_id, reviewer_name, star_rating, review_text) VALUES
(1, 'Rohit Sharma', 5, 'Very fresh and authentic taste. Loved it.'),
(1, 'Priya Verma', 4, 'Good quality and packaging. Worth buying.'),
(1, 'Amit Kumar', 5, 'Amazing taste. Will order again.'),
(2, 'Rohit Sharma', 5, 'Very fresh and authentic taste. Loved it.'),
(2, 'Priya Verma', 4, 'Good quality and packaging. Worth buying.'),
(2, 'Amit Kumar', 5, 'Amazing taste. Will order again.');

-- ------------------------------------------------------------
-- 5. Marketplaces (Where else the brand sells)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS marketplaces;
CREATE TABLE marketplaces (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    marketplace_name TEXT NOT NULL,
    url             TEXT
);

INSERT INTO marketplaces (marketplace_name, url) VALUES
('Amazon', 'https://www.amazon.in/stores/ShuddhSwad/page/FE30688F-669A-452E-A342-EFEB49021BB3'),
('Blinkit', 'https://blinkit.com/dc/?collection_filters=W3siYnJhbmRfaWQiOls1ODY2M119XQ%3D%3D&collection_name=Shuddh+Swad'),
('Instamart', NULL),
('JioMart', 'https://www.jiomart.com/groceries/b/shuddh-swad/229361'),
('Flipkart', 'https://www.flipkart.com/search?q=shuddh%20swad%20thekua'),
('Meesho', 'https://www.meesho.com/shuddhswad');

-- ------------------------------------------------------------
-- 6. Press / Media Mentions
-- ------------------------------------------------------------
DROP TABLE IF EXISTS press_mentions;
CREATE TABLE press_mentions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    publication     TEXT NOT NULL,
    url             TEXT
);

INSERT INTO press_mentions (publication, url) VALUES
('NDTV', 'https://ndtv.in/lifestyle/how-two-bihar-teens-turned-thekua-1-crore-business-story-of-shuddh-swad-thekua-brand-food-startup-india-bihar-entrepreneurs-kailash-and-jayant-9544965'),
('The Economic Times', 'https://m.economictimes.com/news/new-updates/with-10000-and-a-home-recipe-two-bengal-teens-turned-chhath-pujas-thekua-into-a-1-crore-business/amp_articleshow/124988740.cms'),
('News18', 'https://www.news18.com/amp/viral/16-year-old-friends-from-bihar-create-thekua-brand-9669097.html'),
('The Better India', 'https://www.instagram.com/reel/DQWnAmSEszb/?igsh=NW13c2MyNjNkdDVl'),
('DNA India', 'https://www.dnaindia.com/lifestyle/report-how-2-bihar-teenagers-turned-chhath-puja-favourite-snack-thekua-into-a-rs-1-crore-business-3186137'),
('Moneymint', 'https://moneymint.com/how-2-teenagers-turned-indian-snacks-into-a-rs-1-cr-business-in-1-year/'),
('Latestly', 'https://www.latestly.com/social-viral/shuddh-swad-thekua-a-marketing-lesson-for-all-brands-know-what-it-is-and-who-are-the-owners-of-this-new-instagram-sensation-start-up-6865858.html'),
('Snackfax', 'https://snackfax.com/business/internet-is-loving-these-two-founders-on-a-mission-to-build-a-%E2%82%B91-crore-brand-selling-thekua-and-more/'),
('Inshorts', 'https://inshorts.com/en/news/teen-duo-turns-thekua-into--1-cr-brand-with-shuddh-swad-1754556294004'),
('Mathrubhumi', 'https://www.mathrubhumi.com/food/features/indian-snacks-revived-shudh-swad-teens-r5rtt3wz');

-- ------------------------------------------------------------
-- 7. Site Navigation / Key Pages (useful for agent routing)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS site_pages;
CREATE TABLE site_pages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    page_name       TEXT NOT NULL,
    url             TEXT NOT NULL
);

INSERT INTO site_pages (page_name, url) VALUES
('Home', 'https://shuddhswad.shop/'),
('Orders / Account', 'https://shuddhswad.shop/account'),
('Track Order', 'https://shuddhswad.shop/a/track'),
('All Products', 'https://shuddhswad.shop/collections/all'),
('Return Policy', 'https://shuddhswad.shop/pages/return'),
('About Us', 'https://shuddhswad.shop/pages/about-us'),
('Contact Us', 'https://shuddhswad.shop/pages/contact_us'),
('Shipping Policy', 'https://shuddhswad.shop/policies/shipping-policy'),
('Terms of Service', 'https://shuddhswad.shop/policies/terms-of-service'),
('Privacy Policy', 'https://shuddhswad.shop/policies/privacy-policy'),
('FAQ', 'https://shuddhswad.shop/pages/faq'),
('Login', 'https://shuddhswad.shop/customer_authentication/redirect?locale=en&region_country=IN'),
('Cart', 'https://shuddhswad.shop/cart');

-- ------------------------------------------------------------
-- 8. FAQs (from /pages/faq)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS faqs;
CREATE TABLE faqs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category        TEXT NOT NULL,
    question        TEXT NOT NULL,
    answer          TEXT NOT NULL
);

INSERT INTO faqs (category, question, answer) VALUES
('Product & Quality', 'What exactly is Thekua?',
 'Thekua is a traditional Indian sweet snack from Bihar and Jharkhand, especially loved during Chhath Puja. Crafted by deep-frying a dough of wheat flour, semolina, coconut, and ghee — crispy exterior, soft flavorful inside.'),
('Product & Quality', 'What varieties of Thekua do you sell?',
 'Two classic varieties: Sugar (Cheeni) Thekua and Jaggery (Gud) Thekua. (Note: site product pages also list an Elaichi/cardamom variant.)'),
('Product & Quality', 'What is the shelf life and how do I store it?',
 'Stays fresh for up to 45 days per FAQ page (individual product pages state 90 days — verify current figure). Store in an airtight container in a cool, dry place away from direct sunlight.'),
('Ordering & Gifting', 'How do I place an order?',
 'Go to shuddhswad.shop, pick products, add to cart, and check out securely.'),
('Ordering & Gifting', 'Can I gift Shuddh Swad snacks?',
 'Yes — enter the recipient''s shipping address at checkout; a personalized note can be added.'),
('Payment & Shipping', 'What payment methods are available?',
 'Credit/Debit Cards, Netbanking, UPI, popular digital wallets, and Cash on Delivery (COD).'),
('Payment & Shipping', 'What are the delivery charges?',
 'Prepaid orders: free delivery. COD: extra ₹50 paid online, remainder paid on delivery. No other hidden charges.'),
('Payment & Shipping', 'How can I track my order?',
 'A tracking link is sent via email and WhatsApp after shipping. Order status also viewable in the "Track Orders" section using the Order ID.'),
('Returns & Support', 'What is your return and damage policy?',
 'Returns accepted within 2 days of delivery if unused and in original packaging. For damaged products, contact support immediately with photos.'),
('Returns & Support', 'How can I get in touch?',
 'Email contact@shuddhswad.shop, call +91 8016380734, or message @shuddhswad49 on Instagram.');

-- ------------------------------------------------------------
-- Notes for future AI Agent build:
--  * This is a read-only knowledge snapshot (no order/customer
--    transactional data — site requires login for that).
--  * Re-scrape periodically: prices, stock/variant availability,
--    ratings, and shelf-life figures may change or conflict
--    (FAQ says 45 days, product pages say 90 days — confirm).
--  * Elaichi Thekua variant pricing unconfirmed (429 rate-limit
--    on fetch) — re-fetch https://shuddhswad.shop/products/elachi-thekua
--  * WhatsApp number doubles as support channel: +91 8016380734
-- ============================================================
