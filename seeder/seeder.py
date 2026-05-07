import psycopg2
import os
import time
import random
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
            print(f"Wating for database... ({10 - retries}/10)")
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
    print("✅ Imágenes vinculadas correctamente.")
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


def seed_conversations(conn, customer_ids, num_conversations=25):
    print(f"Inserting {num_conversations} conversations...")
    titles = [
        "Consulta sobre medicamentos para el dolor",
        "Pregunta sobre antibióticos y efectos secundarios",
        "Información sobre vitaminas para el sistema inmune",
        "Duda sobre dosis de antiinflamatorios",
        "Asesoría en productos dermatológicos para acné",
        "Consulta sobre antigripales y contraindicaciones",
        "Disponibilidad de medicamentos crónicos",
        "Preguntas sobre almacenamiento de insulina",
        "Interacciones entre medicamentos",
        "Sustitutos genéricos para analgésicos",
    ]
    conversation_ids = []
    with conn.cursor() as cur:
        for _ in range(num_conversations):
            title = random.choice(titles)
            c_id = random.choice(customer_ids)
            created_at = fake.date_time_this_year()

            cur.execute(
                """INSERT INTO conversations (title, costumers_id, created_at) 
                   VALUES (%s, %s, %s) RETURNING id;""",
                (title, c_id, created_at),
            )
            conversation_ids.append(cur.fetchone()[0])
    conn.commit()
    return conversation_ids


def seed_messages(conn, conversation_ids):
    print(f"Generating messages for {len(conversation_ids)} conversations...")
    with conn.cursor() as cur:
        for conv_id in conversation_ids:
            num_messages = random.randint(2, 6)
            current_time = fake.date_time_this_year()
            for i in range(num_messages):
                sender = "user" if i % 2 == 0 else "assistant"
                if sender == "user":
                    content = f"{fake.sentence(nb_words=10)}?"
                else:
                    content = f"Based on your pharmaceutical inquiry, {fake.paragraph(nb_sentences=2)}"
                image_url = None
                if sender == "user" and random.random() < 0.2:  # 20% de probabilidad
                    image_url = (
                        f"https://amazonaws.com_{random.randint(1000, 9999)}.jpg"
                    )
                cur.execute(
                    """INSERT INTO messages (sender, conversations_id, message_content, images, created_at) 
                       VALUES (%s, %s, %s, %s, %s);""",
                    (sender, conv_id, content, image_url, current_time),
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

    # Customers. seeders and suppliers
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

    # AI and interactions
    conv_ids = seed_conversations(conn, cust_ids, 15)
    seed_messages(conn, conv_ids)

    print("Seeder completed.")
    conn.close()

if __name__ == "__main__":
    main()
