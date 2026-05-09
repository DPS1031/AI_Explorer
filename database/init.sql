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
    address VARCHAR(255) NOT NULL,
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

CREATE TABLE IF NOT EXISTS conversations(
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NULL,
    costumers_id INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_id_costumers FOREIGN KEY (costumers_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS messages(
    id SERIAL PRIMARY KEY,
    sender VARCHAR(255) NOT NULL,
    conversations_id INTEGER NOT NULL,
    message_content TEXT,
    images VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_id_conversation FOREIGN KEY (conversations_id) REFERENCES conversations(id),
    CHECK (
        sender IN ('assistant', 'user')
    )
);