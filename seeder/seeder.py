import psycopg2
import os
import time
import random
import hashlib
from dotenv import load_dotenv
from faker import Faker

load_dotenv()
fake = Faker("es_CO")
fake_en = Faker("en_US")


# SECTION 2: Conection with retries
def get_connection():
    retries = 10
    while retries > 0:
        try:
            conn = psycopg2.connect(
                host="postgres",
                database=os.getenv("POSTGRES_DB"),
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD"),
            )
            return conn
        except psycopg2.OperationalError:
            retries -= 1
            print(f"Waiting for database... ({10 - retries}/10)")
            time.sleep(3)
    raise Exception("Couldn't connect to the database after 10 tries")


# SECTION 3: Verification of existing data
def database_has_data(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM customers;")
        count = cur.fetchone()[0]
        return count > 0


# SECTION 4: Insertion Functions
def seed_categories(conn):
    categories_en = [
        "Analgesics",
        "Antibiotics",
        "Vitamins",
        "Anti-inflammatories",
        "Cold and Flu",
        "Dermatologicals",
    ]
    descriptions = [
        "Effective relief for minor aches, pains, and fever reduction management.",
        "Powerful medications designed to inhibit growth or destroy microorganisms and bacteria.",
        "Essential dietary supplements to support immune system health and daily vitality.",
        "Formulated to reduce swelling, pain, and redness in tissues and joints.",
        "Comprehensive treatment for nasal congestion, cough, and common cold symptoms.",
        "Specialized care solutions for skin conditions, irritations, and therapeutic treatments.",
    ]
    categories_ids = []
    print(f"Inserting {categories_en} categories...")
    with conn.cursor() as cur:
        for name, desc in zip(categories_en, descriptions):
            cur.execute(
                "INSERT INTO categories (name, description) VALUES (%s, %s) RETURNING id;",
                (name, desc),
            )
            categories_ids.append(cur.fetchone()[0])
    conn.commit()
    category_map = dict(zip(categories_en, categories_ids))
    print(f"✅ {categories_en} categories inserted.")
    return category_map


def seed_suppliers(conn):
    suppliers = [
        "Global Health Logistics Co.",
        "MediCare Pharma Solutions",
        "BioSynthetix Distributors",
        "Northern Star Medical Supplies",
        "Apex LifeScience Wholesale",
    ]
    print(f"Inserting {suppliers} suppliers...")
    suppliers_ids = []
    with conn.cursor() as cur:
        for name in suppliers:
            email = fake.unique.email()
            contact_number = fake.phone_number()
            cur.execute(
                "INSERT INTO suppliers (name, email, contact_number) VALUES (%s, %s, %s) RETURNING id;",
                (name, email, contact_number),
            )
            suppliers_ids.append(cur.fetchone()[0])
    conn.commit()
    return suppliers_ids


def seed_customers(conn, num_records=10):
    print(f"Inserting {num_records} customers...")
    customer_ids = []
    with conn.cursor() as cur:
        for _ in range(num_records):
            name = fake.name()
            email = fake.unique.email()
            contact_number = fake.phone_number()
            address = fake.address()
            created_at = fake.past_datetime()
            cur.execute(
                "INSERT INTO customers (name, email, contact_number, address, created_at) VALUES (%s, %s, %s, %s, %s) RETURNING id;",
                (name, email, contact_number, address, created_at),
            )
            customer_ids.append(cur.fetchone()[0])
    conn.commit()
    return customer_ids


def seed_products(conn, category_map, supplier_ids):
    medications_by_category = {
        "Analgesics": [
            {
                "name": "Acetaminophen",
                "description": "Analgesic and antipyretic drug.",
                "medication_dosage": "500mg",
                "dosage_form": "Tablet",
                "laboratory": "Genfar",
                "indication_and_symptoms": "Headache and fever.",
            },
            {
                "name": "Ibuprofen",
                "description": "Nonsteroidal anti-inflammatory drug (NSAID).",
                "medication_dosage": "400mg",
                "dosage_form": "Capsule",
                "laboratory": "Bayer",
                "indication_and_symptoms": "Muscle pain and inflammation.",
            },
            {
                "name": "Naproxen",
                "description": "Long-acting NSAID.",
                "medication_dosage": "550mg",
                "dosage_form": "Tablet",
                "laboratory": "Roche",
                "indication_and_symptoms": "Menstrual cramps and severe pain.",
            },
            {
                "name": "Tramadol",
                "description": "Opioid pain medication.",
                "medication_dosage": "50mg",
                "dosage_form": "Capsule",
                "laboratory": "Grünenthal",
                "indication_and_symptoms": "Moderate to severe pain.",
            },
            {
                "name": "Diclofenac",
                "description": "Potent anti-inflammatory and analgesic.",
                "medication_dosage": "50mg",
                "dosage_form": "Tablet",
                "laboratory": "Novartis",
                "indication_and_symptoms": "Arthritis and joint pain.",
            },
        ],
        "Antibiotics": [
            {
                "name": "Amoxicillin",
                "description": "Broad-spectrum penicillin antibiotic.",
                "medication_dosage": "500mg",
                "dosage_form": "Capsule",
                "laboratory": "Sandoz",
                "indication_and_symptoms": "Bacterial infections.",
            },
            {
                "name": "Azithromycin",
                "description": "Macrolide antibiotic for respiratory infections.",
                "medication_dosage": "500mg",
                "dosage_form": "Tablet",
                "laboratory": "Pfizer",
                "indication_and_symptoms": "Pneumonia and bronchitis.",
            },
            {
                "name": "Ciprofloxacin",
                "description": "Fluoroquinolone antibiotic.",
                "medication_dosage": "500mg",
                "dosage_form": "Tablet",
                "laboratory": "Bayer",
                "indication_and_symptoms": "Urinary tract infections.",
            },
            {
                "name": "Clindamycin",
                "description": "Antibiotic for serious infections.",
                "medication_dosage": "300mg",
                "dosage_form": "Capsule",
                "laboratory": "Pfizer",
                "indication_and_symptoms": "Skin and soft tissue infections.",
            },
            {
                "name": "Metronidazole",
                "description": "Antibiotic and antiprotozoal medication.",
                "medication_dosage": "500mg",
                "dosage_form": "Tablet",
                "laboratory": "Flagyl",
                "indication_and_symptoms": "Infections in the GI tract.",
            },
        ],
        "Vitamins": [
            {
                "name": "Vitamin C",
                "description": "Essential water-soluble vitamin.",
                "medication_dosage": "1000mg",
                "dosage_form": "Effervescent tablet",
                "laboratory": "Redoxon",
                "indication_and_symptoms": "Immune system support.",
            },
            {
                "name": "Vitamin D3",
                "description": "Fat-soluble vitamin for bone health.",
                "medication_dosage": "2000 IU",
                "dosage_form": "Softgel",
                "laboratory": "Nature Made",
                "indication_and_symptoms": "Calcium absorption support.",
            },
            {
                "name": "B-Complex",
                "description": "Group of B vitamins for energy metabolism.",
                "medication_dosage": "Standard",
                "dosage_form": "Tablet",
                "laboratory": "Solgar",
                "indication_and_symptoms": "Nervous system support.",
            },
            {
                "name": "Folic Acid",
                "description": "Vitamin B9 essential for cell division.",
                "medication_dosage": "5mg",
                "dosage_form": "Tablet",
                "laboratory": "Genfar",
                "indication_and_symptoms": "Prenatal support.",
            },
            {
                "name": "Multivitamin",
                "description": "Complete blend of essential nutrients.",
                "medication_dosage": "Daily",
                "dosage_form": "Gummy",
                "laboratory": "Centrum",
                "indication_and_symptoms": "General health maintenance.",
            },
        ],
        "Anti-inflammatories": [
            {
                "name": "Prednisolone",
                "description": "Glucocorticoid steroid.",
                "medication_dosage": "5mg",
                "dosage_form": "Tablet",
                "laboratory": "Pfizer",
                "indication_and_symptoms": "Severe allergic reactions.",
            },
            {
                "name": "Meloxicam",
                "description": "NSAID with focus on joint health.",
                "medication_dosage": "15mg",
                "dosage_form": "Tablet",
                "laboratory": "Boehringer Ingelheim",
                "indication_and_symptoms": "Osteoarthritis.",
            },
            {
                "name": "Dexamethasone",
                "description": "Long-acting corticosteroid.",
                "medication_dosage": "4mg",
                "dosage_form": "Tablet",
                "laboratory": "Merck",
                "indication_and_symptoms": "Inflammatory conditions.",
            },
            {
                "name": "Celecoxib",
                "description": "COX-2 selective NSAID.",
                "medication_dosage": "200mg",
                "dosage_form": "Capsule",
                "laboratory": "Pfizer",
                "indication_and_symptoms": "Acute pain and arthritis.",
            },
            {
                "name": "Ketorolac",
                "description": "Short-term management of moderate pain.",
                "medication_dosage": "10mg",
                "dosage_form": "Tablet",
                "laboratory": "Laboratorios MK",
                "indication_and_symptoms": "Post-surgical pain.",
            },
        ],
        "Cold and Flu": [
            {
                "name": "Loratadine",
                "description": "Second-generation antihistamine.",
                "medication_dosage": "10mg",
                "dosage_form": "Tablet",
                "laboratory": "Sanofi",
                "indication_and_symptoms": "Allergy symptoms and sneezing.",
            },
            {
                "name": "Salbutamol",
                "description": "Short-acting bronchodilator.",
                "medication_dosage": "100mcg",
                "dosage_form": "Inhaler",
                "laboratory": "GSK",
                "indication_and_symptoms": "Asthma and bronchospasm.",
            },
            {
                "name": "Cetirizine",
                "description": "Antihistamine for seasonal allergies.",
                "medication_dosage": "10mg",
                "dosage_form": "Tablet",
                "laboratory": "UCB Pharma",
                "indication_and_symptoms": "Hay fever and itchy eyes.",
            },
            {
                "name": "Fexofenadine",
                "description": "Non-drowsy antihistamine.",
                "medication_dosage": "120mg",
                "dosage_form": "Tablet",
                "laboratory": "Sanofi",
                "indication_and_symptoms": "Urticaria and allergy relief.",
            },
            {
                "name": "Budesonide",
                "description": "Anti-inflammatory corticosteroid.",
                "medication_dosage": "200mcg",
                "dosage_form": "Inhalation powder",
                "laboratory": "AstraZeneca",
                "indication_and_symptoms": "COPD and asthma.",
            },
        ],
        "Dermatologicals": [
            {
                "name": "Betamethasone",
                "description": "Corticosteroid for skin and systemic use.",
                "medication_dosage": "0.1%",
                "dosage_form": "Cream",
                "laboratory": "Schering-Plough",
                "indication_and_symptoms": "Dermatitis and skin inflammation.",
            },
            {
                "name": "Clotrimazole",
                "description": "Antifungal medication.",
                "medication_dosage": "1%",
                "dosage_form": "Topical cream",
                "laboratory": "Bayer",
                "indication_and_symptoms": "Fungal skin infections.",
            },
            {
                "name": "Ketoconazole",
                "description": "Broad-spectrum antifungal.",
                "medication_dosage": "200mg",
                "dosage_form": "Cream",
                "laboratory": "Janssen",
                "indication_and_symptoms": "Seborrheic dermatitis.",
            },
            {
                "name": "Hydrocortisone",
                "description": "Low-potency topical steroid.",
                "medication_dosage": "1%",
                "dosage_form": "Ointment",
                "laboratory": "Genfar",
                "indication_and_symptoms": "Itching and minor rashes.",
            },
            {
                "name": "Benzoyl Peroxide",
                "description": "Topical treatment for acne.",
                "medication_dosage": "5%",
                "dosage_form": "Gel",
                "laboratory": "Galderma",
                "indication_and_symptoms": "Acne vulgaris.",
            },
        ],
    }
    print(f"Inserting medications")
    products_ids = []
    with conn.cursor() as cur:
        for cat_name, products in medications_by_category.items():
            category_id = category_map.get(cat_name)
            for prod in products:
                suppliers_id = random.choice(supplier_ids)
                price = fake.random_int(min=5000, max=80000)
                created_at = fake.past_datetime()
                updated_at = fake.date_time_this_year()
                cur.execute(
                    """INSERT INTO products 
                        (name, description, price, medication_dosage, dosage_form, laboratory, 
                            indication_and_symptoms, category_id, supplier_id, created_at, updated_at) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id ;""",
                    (
                        prod["name"],
                        prod["description"],
                        price,
                        prod["medication_dosage"],
                        prod["dosage_form"],
                        prod["laboratory"],
                        prod["indication_and_symptoms"],
                        category_id,
                        suppliers_id,
                        created_at,
                        updated_at,
                    ),
                )
                products_ids.append(cur.fetchone()[0])
    conn.commit()
    return products_ids


def seed_product_images(conn, products_id):
    print(f"Generating images for {len(products_id)} products...")
    product_images_ids = []
    with conn.cursor() as cur:
        for p_id in products_id:
            image_url = f"https://pharmacy-images.s3.amazonaws.com/products/{p_id}.jpg"
            cur.execute(
                "INSERT INTO product_images (products_id, image_url) VALUES (%s, %s) RETURNING id;",
                (p_id, image_url),
            )
            product_images_ids.append(cur.fetchone()[0])
    conn.commit()
    print("✅ Product images linked successfully.")
    return product_images_ids


def seed_inventory(conn, products_id):
    print(f"Inserting inventory {len(products_id)} products...")
    inventory_ids = []
    with conn.cursor() as cur:
        for p_id in products_id:
            actual_stock = fake.random_int(min=10, max=200)
            minimum_stock = fake.random_int(min=5, max=30)
            last_update = fake.date_time_this_year()
            cur.execute(
                """INSERT INTO inventory (products_id, actual_stock, minimum_stock, last_update) 
                   VALUES (%s, %s, %s, %s) RETURNING id;""",
                (p_id, actual_stock, minimum_stock, last_update),
            )
            inventory_ids.append(cur.fetchone()[0])
    conn.commit()
    return inventory_ids


def seed_orders(conn, customer_ids, num_orders=20):
    print(f"Inserting {num_orders} orders...")
    order_ids = []
    states = ["pending", "confirmed", "delivered", "cancelled"]
    with conn.cursor() as cur:
        for _ in range(num_orders):
            is_registered = random.choice([True, False])
            if is_registered and customer_ids:
                c_id = random.choice(customer_ids)
                c_email = fake.email()
            else:
                c_id = None
                c_email = fake.email()
            state = random.choice(states)
            total = round(random.uniform(20.0, 500.0), 2)
            created_at = fake.date_time_this_year()
            cur.execute(
                """INSERT INTO orders 
                   (customers_id, contact_email, order_state, total, created_at, updated_at) 
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;""",
                (c_id, c_email, state, total, created_at, created_at),
            )
            order_ids.append(cur.fetchone()[0])
    conn.commit()
    return order_ids


def seed_order_items(conn, order_ids, products_id):
    print(f"Inserting items {len(order_ids)} orders...")
    with conn.cursor() as cur:
        for o_id in order_ids:
            selected_products = random.sample(products_id, k=random.randint(1, 3))
            for p_id in selected_products:
                price = round(random.uniform(10.0, 150.0), 2)
                quantity = fake.random_int(min=1, max=5)
                cur.execute(
                    """INSERT INTO order_items (orders_id, products_id, products_price, quantity) 
                       VALUES (%s, %s, %s, %s);""",
                    (o_id, p_id, price, quantity),
                )
    conn.commit()


def seed_order_status_history(conn, order_ids):
    print("Generating an order history...")
    status_flow = ["pending", "confirmed", "delivered", "cancelled"]
    with conn.cursor() as cur:
        for o_id in order_ids:
            cur.execute(
                "SELECT order_state, created_at FROM orders WHERE id = %s;", (o_id,)
            )
            final_state, created_at = cur.fetchone()
            current_time = created_at
            cur.execute(
                "INSERT INTO order_status_history (orders_id, order_state, changed_at, note) VALUES (%s, %s, %s, %s);",
                (o_id, "pending", current_time, "Initial order placement."),
            )
            if final_state != "pending":
                if final_state == "cancelled":
                    states_to_add = ["cancelled"]
                else:
                    idx = status_flow.index(final_state)
                    states_to_add = status_flow[1 : idx + 1]
                for state in states_to_add:
                    current_time = fake.date_time_between(
                        start_date=current_time, end_date="+2d"
                    )
                    cur.execute(
                        "INSERT INTO order_status_history (orders_id, order_state, changed_at, note) VALUES (%s, %s, %s, %s);",
                        (
                            o_id,
                            state,
                            current_time,
                            f"Order status updated to {state}.",
                        ),
                    )
    conn.commit()


def hash_password(password: str) -> str:
    """Generates a secure password hash using PBKDF2."""
    salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return salt.hex() + ":" + pwd_hash.hex()


def seed_users(conn):
    """Creates test users for the login system."""
    print("Inserting test users...")
    test_users = [
        {"name": "David Admin", "email": "david@pharmacy.com", "password": "123456"},
        {"name": "Maria Garcia", "email": "maria@pharmacy.com", "password": "123456"},
        {"name": "Carlos Lopez", "email": "carlos@pharmacy.com", "password": "123456"},
    ]
    user_ids = []
    with conn.cursor() as cur:
        for user in test_users:
            password_hash = hash_password(user["password"])
            cur.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s) RETURNING id;",
                (user["name"], user["email"], password_hash),
            )
            user_ids.append(cur.fetchone()[0])
    conn.commit()
    print(f"✅ {len(test_users)} test users inserted.")
    print("   📧 Login credentials:")
    for user in test_users:
        print(f"      - {user['email']} / {user['password']}")
    return user_ids


def seed_conversations(conn, user_ids, num_conversations=25):
    print(f"Inserting {num_conversations} conversations...")
    titles = [
        "Pain medication recommendations",
        "Antibiotics side effects inquiry",
        "Vitamins for immune system support",
        "Anti-inflammatory dosage question",
        "Dermatological products for acne",
        "Cold and flu medication options",
        "Chronic medication availability",
        "Insulin storage guidelines",
        "Drug interaction concerns",
        "Generic substitutes for analgesics",
        "Best vitamins for energy and fatigue",
        "Allergy medication without drowsiness",
        "Post-surgery pain management",
        "Children's fever medication dosage",
        "Skin rash treatment options",
    ]
    conversation_ids = []
    with conn.cursor() as cur:
        for _ in range(num_conversations):
            title = random.choice(titles)
            u_id = random.choice(user_ids)
            created_at = fake.date_time_this_year()

            cur.execute(
                """INSERT INTO conversations (title, user_id, created_at) 
                   VALUES (%s, %s, %s) RETURNING id;""",
                (title, u_id, created_at),
            )
            conversation_ids.append(cur.fetchone()[0])
    conn.commit()
    return conversation_ids


def seed_messages(conn, conversation_ids):
    print(f"Generating messages for {len(conversation_ids)} conversations...")

    # Contextual message pairs (user question, assistant answer) grouped by topic
    message_templates = {
        "Pain medication recommendations": [
            ("What do you recommend for chronic back pain?", "For chronic back pain, I'd suggest starting with Ibuprofen 400mg or Naproxen 550mg. Both are effective NSAIDs. If the pain is severe, Tramadol 50mg may be appropriate but requires a prescription."),
            ("Is Acetaminophen safe to take daily?", "Acetaminophen 500mg is generally safe for short-term daily use, but prolonged use exceeding 3g per day can cause liver damage. I'd recommend consulting your doctor for long-term pain management."),
            ("Can I combine Ibuprofen with Acetaminophen?", "Yes, you can alternate between Ibuprofen and Acetaminophen as they work through different mechanisms. However, avoid taking multiple NSAIDs together like Ibuprofen and Naproxen."),
        ],
        "Antibiotics side effects inquiry": [
            ("What are the common side effects of Amoxicillin?", "Common side effects of Amoxicillin include nausea, diarrhea, and skin rash. If you experience difficulty breathing or severe swelling, seek immediate medical attention as it could indicate an allergic reaction."),
            ("How long should I take Azithromycin?", "Azithromycin is typically prescribed as a 5-day course (500mg on day 1, then 250mg for days 2-5). It's important to complete the full course even if you feel better to prevent antibiotic resistance."),
            ("Can I drink alcohol while on Metronidazole?", "No, you should absolutely avoid alcohol while taking Metronidazole and for at least 48 hours after finishing the course. The combination can cause severe nausea, vomiting, and abdominal cramps."),
        ],
        "Vitamins for immune system support": [
            ("What vitamins should I take to boost my immune system?", "For immune support, I recommend Vitamin C 1000mg daily, Vitamin D3 2000 IU (especially if you have limited sun exposure), and a B-Complex for overall energy. Our Multivitamin gummies from Centrum are also a great all-in-one option."),
            ("Is it okay to take multiple vitamins at once?", "Yes, most vitamins can be taken together. However, take fat-soluble vitamins (D, E, A, K) with food for better absorption. Space out calcium and iron supplements as they compete for absorption."),
            ("Do I need Vitamin D if I spend time outdoors?", "Even with outdoor time, many people are deficient in Vitamin D, especially during winter months. A blood test can confirm your levels. Our Vitamin D3 2000 IU softgels from Nature Made are a popular choice."),
        ],
        "Anti-inflammatory dosage question": [
            ("What's the correct dosage for Meloxicam?", "Meloxicam is typically prescribed at 7.5mg to 15mg once daily for osteoarthritis. Always take it with food to reduce stomach irritation. Don't exceed 15mg per day."),
            ("How does Prednisolone work for inflammation?", "Prednisolone is a corticosteroid that suppresses the immune system's inflammatory response. It's very effective for severe allergic reactions and autoimmune conditions, but should only be used short-term due to side effects."),
            ("Is Celecoxib safer for the stomach than Ibuprofen?", "Yes, Celecoxib is a COX-2 selective inhibitor, which means it causes fewer gastrointestinal side effects compared to traditional NSAIDs like Ibuprofen. However, it still carries cardiovascular risks with long-term use."),
        ],
        "Dermatological products for acne": [
            ("What's the best treatment for mild acne?", "For mild acne, I recommend starting with Benzoyl Peroxide 5% gel from Galderma. Apply a thin layer to affected areas once daily. If irritation occurs, reduce to every other day until your skin adjusts."),
            ("Can I use Hydrocortisone on my face?", "Hydrocortisone 1% can be used on the face for short periods (up to 7 days) for conditions like eczema or dermatitis. However, prolonged facial use can thin the skin. It's not recommended for acne treatment."),
            ("What do you have for fungal skin infections?", "For fungal infections, we have Clotrimazole 1% topical cream and Ketoconazole cream. Clotrimazole is great for athlete's foot and ringworm, while Ketoconazole works well for seborrheic dermatitis."),
        ],
        "Cold and flu medication options": [
            ("What can I take for a stuffy nose and cough?", "For nasal congestion, Loratadine 10mg is a good non-drowsy antihistamine. If you also have a cough with wheezing, Salbutamol inhaler can help open your airways. For general cold symptoms, rest and fluids are essential."),
            ("Which antihistamine won't make me sleepy?", "Fexofenadine 120mg is our best non-drowsy option. Loratadine and Cetirizine are also second-generation antihistamines with minimal sedation, though some people find Cetirizine slightly more sedating."),
            ("I have seasonal allergies, what do you recommend?", "For seasonal allergies, Cetirizine 10mg is very effective for hay fever and itchy eyes. Take it once daily. If nasal symptoms are predominant, Budesonide nasal spray provides targeted relief with minimal systemic effects."),
        ],
        "Chronic medication availability": [
            ("Do you have Metformin in stock?", "I'd need to check our current inventory for Metformin. We typically carry 500mg and 850mg tablets. Would you like me to check availability and pricing for you?"),
            ("Can I get a 3-month supply of my blood pressure medication?", "We can provide up to a 90-day supply for chronic medications with a valid prescription. This often comes with cost savings compared to monthly refills. Please bring your prescription and I'll check what we can arrange."),
            ("What generic options do you have for cholesterol medication?", "We carry several generic statins including Atorvastatin and Simvastatin, which are equivalent to brand-name Lipitor and Zocor. Generics offer the same efficacy at a significantly lower cost."),
        ],
        "Insulin storage guidelines": [
            ("How should I store my insulin at home?", "Unopened insulin should be stored in the refrigerator at 2-8°C (36-46°F). Once opened, most insulin pens can be kept at room temperature (below 30°C) for up to 28 days. Never freeze insulin."),
            ("What happens if insulin gets too warm?", "Insulin exposed to temperatures above 30°C (86°F) degrades faster and loses effectiveness. If your insulin has been left in a hot car or direct sunlight, it's safer to discard it and use a new vial or pen."),
            ("Can I travel with insulin on a plane?", "Yes, insulin is allowed in carry-on luggage. Keep it in an insulated travel case with ice packs. Carry a doctor's letter and keep it in original packaging. Never put insulin in checked baggage as the cargo hold can freeze."),
        ],
        "Drug interaction concerns": [
            ("Can I take Ibuprofen with my blood pressure medication?", "NSAIDs like Ibuprofen can reduce the effectiveness of blood pressure medications and may increase blood pressure. Acetaminophen is generally a safer pain relief option if you're on antihypertensives."),
            ("Are there interactions between Azithromycin and antacids?", "Yes, antacids containing aluminum or magnesium can reduce Azithromycin absorption. Take Azithromycin at least 1 hour before or 2 hours after antacids to ensure full effectiveness."),
            ("I'm on Warfarin, what pain relievers are safe?", "With Warfarin, avoid all NSAIDs (Ibuprofen, Naproxen, Aspirin) as they increase bleeding risk. Acetaminophen in moderate doses (up to 2g/day) is the safest option. Always inform your doctor about any new medications."),
        ],
        "Generic substitutes for analgesics": [
            ("Is generic Ibuprofen as effective as Advil?", "Yes, generic Ibuprofen contains the same active ingredient in the same dosage as Advil. The FDA requires generics to be bioequivalent, meaning they work the same way in your body. The only difference is price."),
            ("What's the cheapest option for headache relief?", "Generic Acetaminophen 500mg tablets from Genfar are our most affordable option for headache relief. They're equally effective as brand-name Tylenol at a fraction of the cost."),
            ("Do you have a generic version of Celebrex?", "Yes, we carry Celecoxib 200mg capsules which is the generic equivalent of Celebrex. It's a COX-2 selective anti-inflammatory that's easier on the stomach than traditional NSAIDs."),
        ],
        "Best vitamins for energy and fatigue": [
            ("I've been feeling tired all the time, what vitamins help?", "Persistent fatigue can be helped with B-Complex vitamins (especially B12), Iron supplements, and Vitamin D3. I'd also recommend getting blood work done to check for deficiencies. Our Solgar B-Complex is a popular choice."),
            ("What's the difference between B12 and B-Complex?", "B12 is a single vitamin focused on nerve function and red blood cell production. B-Complex contains all 8 B vitamins working together for energy metabolism, brain function, and cell health. If you're generally fatigued, B-Complex covers more bases."),
            ("Can Vitamin D deficiency cause tiredness?", "Absolutely. Vitamin D deficiency is one of the most common causes of unexplained fatigue. Our Vitamin D3 2000 IU softgels from Nature Made are recommended for most adults. Consider taking it with a fatty meal for better absorption."),
        ],
        "Allergy medication without drowsiness": [
            ("I need allergy medicine that won't affect my work", "Fexofenadine 120mg is the least sedating antihistamine available. It's ideal for people who need to stay alert. Take it once daily and it provides 24-hour relief from sneezing, runny nose, and itchy eyes."),
            ("Is Cetirizine really non-drowsy?", "Cetirizine is classified as a second-generation antihistamine with low sedation, but about 10% of people do experience some drowsiness. If that's a concern, Fexofenadine or Loratadine are better alternatives for you."),
            ("What about nasal sprays for allergies?", "Budesonide nasal spray is excellent for allergy relief without any drowsiness since it works locally in the nasal passages. It's particularly effective for congestion, which oral antihistamines don't address as well."),
        ],
        "Post-surgery pain management": [
            ("What pain medication is recommended after dental surgery?", "After dental surgery, a combination of Ibuprofen 400mg and Acetaminophen 500mg taken together provides excellent pain relief. For the first 24-48 hours, Ketorolac 10mg may be prescribed for more intense pain."),
            ("How long should I take pain medication after surgery?", "Typically, strong pain medication is needed for 3-5 days post-surgery, then you can transition to milder options. Always follow your surgeon's specific instructions and taper off gradually rather than stopping abruptly."),
            ("Is Tramadol addictive?", "Tramadol does carry a risk of dependence, especially with prolonged use beyond 2 weeks. It's classified as a controlled substance. For post-surgical pain, short-term use under medical supervision is generally safe. Always follow prescribed dosages."),
        ],
        "Children's fever medication dosage": [
            ("What's the right Acetaminophen dose for a 5-year-old?", "For a 5-year-old (approximately 18-20kg), the recommended Acetaminophen dose is 240-300mg every 4-6 hours. Use the children's liquid formulation with the included measuring device. Don't exceed 5 doses in 24 hours."),
            ("Can I give my child Ibuprofen for fever?", "Yes, children's Ibuprofen is safe for kids over 6 months old. For fever above 38.5°C, dose by weight: approximately 5-10mg per kg every 6-8 hours. You can alternate with Acetaminophen if needed, but never give both at the same time."),
            ("When should I take my child to the doctor for fever?", "Seek medical attention if fever exceeds 39.5°C, lasts more than 3 days, is accompanied by rash or stiff neck, or if the child is under 3 months old with any fever. Also if the child appears unusually lethargic or refuses fluids."),
        ],
        "Skin rash treatment options": [
            ("I have a red itchy rash on my arms, what can I use?", "For a general itchy rash, Hydrocortisone 1% ointment applied twice daily can reduce inflammation and itching. If it's widespread, an oral antihistamine like Cetirizine can also help. If it doesn't improve in a week, see a dermatologist."),
            ("Could my rash be a fungal infection?", "Fungal rashes typically have a ring-shaped pattern with clear center, or appear in warm moist areas. If you suspect fungus, Clotrimazole 1% cream applied twice daily for 2-4 weeks is the first-line treatment. Keep the area clean and dry."),
            ("What's good for eczema flare-ups?", "For eczema flare-ups, Betamethasone 0.1% cream is effective for moderate to severe patches. Apply thinly once or twice daily for up to 2 weeks. Pair with a fragrance-free moisturizer. For mild cases, Hydrocortisone 1% is sufficient."),
        ],
    }

    # Default messages for titles not in the template
    default_messages = [
        ("Hi, I have a question about my medication.", "Of course! I'd be happy to help. What medication are you asking about and what would you like to know?"),
        ("Can you check if a product is in stock?", "I can help with that. Which product are you looking for? I'll check our current inventory for you."),
        ("What would you recommend for general wellness?", "For general wellness, I'd suggest a daily Multivitamin, Vitamin D3 for bone health, and Omega-3 fatty acids for heart health. Regular exercise and a balanced diet are equally important."),
    ]

    with conn.cursor() as cur:
        for conv_id in conversation_ids:
            # Get the conversation title to match messages
            cur.execute("SELECT title FROM conversations WHERE id = %s;", (conv_id,))
            title = cur.fetchone()[0]

            # Get matching messages or use defaults
            available_messages = message_templates.get(title, default_messages)
            num_pairs = random.randint(1, min(3, len(available_messages)))
            selected_pairs = random.sample(available_messages, num_pairs)

            current_time = fake.date_time_this_year()
            for user_msg, assistant_msg in selected_pairs:
                # User message
                image_url = None
                if random.random() < 0.1:
                    image_url = f"https://amazonaws.com_{random.randint(1000, 9999)}.jpg"
                cur.execute(
                    """INSERT INTO messages (sender, conversations_id, message_content, images, created_at) 
                       VALUES (%s, %s, %s, %s, %s);""",
                    ("user", conv_id, user_msg, image_url, current_time),
                )
                current_time = fake.date_time_between(
                    start_date=current_time, end_date="+10m"
                )
                # Assistant message
                cur.execute(
                    """INSERT INTO messages (sender, conversations_id, message_content, images, created_at) 
                       VALUES (%s, %s, %s, %s, %s);""",
                    ("assistant", conv_id, assistant_msg, None, current_time),
                )
                current_time = fake.date_time_between(
                    start_date=current_time, end_date="+10m"
                )
    conn.commit()


# SECTION 5: Main
def main():
    print("🚀 Seeder starting...", flush=True)
    conn = get_connection()
    print("✅ Connected to database", flush=True)
    if database_has_data(conn):
        print("⚠️ Database already has data. Skipping.", flush=True)
        return
    print("📦 Starting data insertion...", flush=True)
    conn = get_connection()
    if database_has_data(conn):
        return

    # Users (for login system)
    user_ids = seed_users(conn)

    # Customers, seeders and suppliers
    sup_ids = seed_suppliers(conn)
    cat_map = seed_categories(conn)
    cust_ids = seed_customers(conn, 10)

    # Products and stock
    prod_ids = seed_products(conn, cat_map, sup_ids)
    seed_inventory(conn, prod_ids)
    seed_product_images(conn, prod_ids)

    # Transactions
    ord_ids = seed_orders(conn, cust_ids, 20)
    seed_order_items(conn, ord_ids, prod_ids)
    seed_order_status_history(conn, ord_ids)

    # AI and interactions (conversations now linked to users, not customers)
    conv_ids = seed_conversations(conn, user_ids, 15)
    seed_messages(conn, conv_ids)

    print("✅ Seeder completed.")
    conn.close()

if __name__ == "__main__":
    main()
