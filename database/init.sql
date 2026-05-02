CREATE TABLE IF NOT EXISTS categories(
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS suppliers(
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    contact_number VARCHAR(20) NOT NULL
);
CREATE TABLE IF NOT EXISTS customers(
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    contact_number VARCHAR(20) NOT NULL,
    direction VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS products(
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    medication_dosage VARCHAR(255) NOT NULL,
    dosage_form VARCHAR(255) NOT NULL,
    laboratory VARCHAR(255) NOT NULL,
    indication_and_symptoms TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_indications_categories FOREIGN KEY (category_id) REFERENCES categories(id),
    CONSTRAINT fk_indications_supliers FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);
CREATE TABLE IF NOT EXISTS product_images(
    id SERIAL PRIMARY KEY,
    products_id INTEGER NOT NULL,
    image_url VARCHAR(500),
    CONSTRAINT fk_id_products FOREIGN KEY (products_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS inventory(
    id SERIAL PRIMARY KEY,
    actual_stock INTEGER NOT NULL DEFAULT 0,
    products_id INTEGER NOT NULL,
    minimum_stock INTEGER NOT NULL,
    last_update TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_id_products FOREIGN KEY (products_id) REFERENCES products(id)
    /*CONSTRAINT fk_updated_date_products FOREIGN KEY (products_last_update) REFERENCES products(updated_at)*/
);
CREATE TABLE IF NOT EXISTS orders(
    id SERIAL PRIMARY KEY,
    customers_id INTEGER,
    contact_email VARCHAR(255),
    order_state VARCHAR(255) NOT NULL DEFAULT 'pending',
    total DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_id_customers FOREIGN KEY (customers_id) REFERENCES customers(id),
    CHECK (
        order_state IN ('pending', 'confirmed', 'delivered', 'cancelled')
    )
);
CREATE TABLE IF NOT EXISTS order_items(
    id SERIAL PRIMARY KEY,
    orders_id INTEGER NOT NULL,
    products_id INTEGER NOT NULL,
    products_price DECIMAL(10, 2) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT fk_id_orders FOREIGN KEY (orders_id) REFERENCES orders(id),
    CONSTRAINT fk_id_products FOREIGN KEY (products_id) REFERENCES products(id)
    /*CONSTRAINT fk_price_products FOREIGN KEY (products_price) REFERENCES products(price),
     CONSTRAINT fk_stock_inventory FOREIGN KEY (inventory_stock) REFERENCES inventory(actual_stock)*/
);
CREATE TABLE IF NOT EXISTS order_status_history(
    id SERIAL PRIMARY KEY,
    orders_id INTEGER NOT NULL,
    order_state VARCHAR(255) NOT NULL DEFAULT 'pending',
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    note TEXT,
    CONSTRAINT fk_id_orders FOREIGN KEY (orders_id) REFERENCES orders(id),
    CHECK (
        order_state IN ('pending', 'confirmed', 'delivered', 'cancelled')
    )
    /*CONSTRAINT fk_state_orders FOREIGN KEY (orders_state) REFERENCES orders(order_state), 
     CONSTRAINT fk_update_orders FOREIGN KEY (orders_update) REFERENCES orders(updated_at)*/
);
-- 1. CATEGORIES (4 Categorías)
INSERT INTO categories (name, description)
VALUES (
        'Analgésicos',
        'Medicamentos diseñados para aliviar o eliminar el dolor físico, ya sea muscular, articular o de cabeza.'
    ),
    (
        'Antibióticos',
        'Fármacos utilizados para tratar infecciones bacterianas; no efectivos contra virus como la gripe.'
    ),
    (
        'Vitaminas',
        'Suplementos para cubrir deficiencias nutricionales y fortalecer el sistema inmunológico.'
    ),
    (
        'Antiinflamatorios',
        'Medicamentos que reducen la inflamación, el enrojecimiento y el dolor en tejidos del cuerpo.'
    );
-- 2. SUPPLIERS (2 Proveedores)
INSERT INTO suppliers (name, email, contact_number)
VALUES (
        'Droguerías Continental',
        'ventas@continental.com',
        '3001112233'
    ),
    (
        'Laboratorios Alianza Pharma',
        'contacto@alianzapharma.com',
        '3154445566'
    );
-- 3. CUSTOMERS (3 Clientes)
INSERT INTO customers (name, email, contact_number, direction)
VALUES (
        'Juan Pérez',
        'juan.perez@email.com',
        '3209876543',
        'Calle 45 #10-20, Bogotá'
    ),
    (
        'María García',
        'm.garcia@email.com',
        '3112223344',
        'Carrera 7 #100-15, Medellín'
    ),
    (
        'Carlos Ruiz',
        'cruiz88@email.com',
        '3005556677',
        'Avenida Siempre Viva 123'
    );
-- 4. PRODUCTS (8 Productos)
INSERT INTO products (
        name,
        description,
        price,
        medication_dosage,
        dosage_form,
        laboratory,
        indication_and_symptoms,
        category_id,
        supplier_id
    )
VALUES -- Analgésicos
    (
        'Acetaminofén 500mg',
        'Analgésico y antipirético de uso común.',
        5500.00,
        '500mg',
        'Tabletas',
        'Genfar',
        'Indicado para el alivio del dolor leve a moderado y para reducir la fiebre.',
        1,
        1
    ),
    (
        'Aspirina (Ácido Acetilsalicílico)',
        'Analgésico y antiagregante plaquetario.',
        12000.00,
        '100mg',
        'Tabletas masticables',
        'Bayer',
        'Alivio de dolores de cabeza y prevención de riesgos cardiovasculares.',
        1,
        1
    ),
    -- Antibióticos
    (
        'Amoxicilina 500mg',
        'Antibiótico de amplio espectro derivado de la penicilina.',
        18000.00,
        '500mg',
        'Cápsulas',
        'MK',
        'Tratamiento de infecciones bacterianas en garganta, oídos y vías urinarias.',
        2,
        2
    ),
    (
        'Azitromicina 500mg',
        'Antibiótico macrólido potente.',
        25000.00,
        '500mg',
        'Tabletas recubiertas',
        'Pfizer',
        'Efectivo contra infecciones respiratorias y de la piel. Esquema corto de 3 días.',
        2,
        2
    ),
    -- Vitaminas
    (
        'Vitamina C + Zinc',
        'Suplemento efervescente para el sistema inmune.',
        32000.00,
        '1g + 10mg',
        'Tabletas efervescentes',
        'Redoxon',
        'Prevención y tratamiento de síntomas del resfriado común.',
        3,
        1
    ),
    (
        'Complejo B',
        'Mezcla de vitaminas B1, B6 y B12.',
        15000.00,
        'Varios',
        'Jarabe',
        'Laboratorios Vida',
        'Indicado para el cansancio físico, estrés y regeneración nerviosa.',
        3,
        2
    ),
    -- Antiinflamatorios
    (
        'Ibuprofeno 600mg',
        'Antiinflamatorio no esteroideo (AINE).',
        8000.00,
        '600mg',
        'Cápsulas blandas',
        'Advil',
        'Reduce la inflamación muscular, dolores menstruales y artritis.',
        4,
        1
    ),
    (
        'Naproxeno 500mg',
        'Potente antiinflamatorio de larga duración.',
        14000.00,
        '500mg',
        'Tabletas',
        'Genfar',
        'Tratamiento de inflamaciones severas, esguinces y dolores articulares.',
        4,
        2
    );
-- 5. PRODUCT_IMAGES
INSERT INTO product_images (products_id, image_url)
VALUES (1, 'http://farmacia.com'),
    (3, 'http://farmacia.com'),
    (7, 'http://farmacia.com');
-- 6. INVENTORY (Stock para los 8 productos)
INSERT INTO inventory (actual_stock, products_id, minimum_stock)
VALUES (100, 1, 20),
    (50, 2, 10),
    (30, 3, 15),
    (25, 4, 5),
    (80, 5, 20),
    (45, 6, 10),
    (60, 7, 15),
    (40, 8, 10);
-- 7. ORDERS (2 Órdenes)
-- Orden 1 para Juan Pérez
INSERT INTO orders (customers_id, contact_email, order_state, total)
VALUES (1, 'juan.perez@email.com', 'confirmed', 43000.00);
-- Orden 2 para María García
INSERT INTO orders (customers_id, contact_email, order_state, total)
VALUES (2, 'm.garcia@email.com', 'pending', 32000.00);
-- 8. ORDER_ITEMS (Detalles de las órdenes)
-- Juan compró Acetaminofén (2) e Ibuprofeno (4)
INSERT INTO order_items (orders_id, products_id, products_price, quantity)
VALUES (1, 1, 5500.00, 2),
    (1, 7, 8000.00, 4);
-- María compró Vitamina C + Zinc (1)
INSERT INTO order_items (orders_id, products_id, products_price, quantity)
VALUES (2, 5, 32000.00, 1);
-- 9. ORDER_STATUS_HISTORY (Historial de estados)
-- Historial Orden 1
INSERT INTO order_status_history (orders_id, order_state, note)
VALUES (1, 'pending', 'Orden recibida por el sistema.'),
    (
        1,
        'confirmed',
        'Pago verificado y productos reservados.'
    );
-- Historial Orden 2
INSERT INTO order_status_history (orders_id, order_state, note)
VALUES (
        2,
        'pending',
        'Esperando validación de pago por transferencia.'
    );