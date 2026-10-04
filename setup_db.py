import sqlite3

# Connect to (and create) the SQLite database
conn = sqlite3.connect('inventory.db')
cursor = conn.cursor()

# Create the inventory table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS stock (
        sku TEXT PRIMARY KEY,
        stock_units INTEGER,
        avg_daily_sales INTEGER
    )
''')

# Insert Milkbasket sample data
data = [
    ('Aashirvaad Whole Wheat Atta 5kg', 120, 50), # 2.4 days cover (Critical)
    ('Amul Taaza Milk 1L', 400, 350),             # 1.1 days cover (Critical)
    ('Tata Salt 1kg', 850, 100)                   # 8.5 days cover (Healthy)
]

cursor.executemany('INSERT OR REPLACE INTO stock VALUES (?, ?, ?)', data)
conn.commit()
conn.close()

print("✅ SQLite Inventory Database created successfully!")