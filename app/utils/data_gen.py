import random
from faker import Faker
from datetime import datetime, timedelta

fake = Faker()

def generate_wealth_data(db_client):
    print("Generating dummy banking data...")
    conn = db_client.get_connection()
    cursor = conn.cursor()

    try:
        # Clear data
        tables = ["portfolio_holdings", "transactions", "advisor_client_mapping", "accounts", "advisors", "users", "account_types"]
        for table in tables:
            cursor.execute(f"DELETE FROM {table}")
        conn.commit()

        # 1. Populating account_types
        account_types = [("Savings", 0.0450), ("Checking", 0.0010), ("Investment", 0.0000), ("Retirement", 0.0550), ("High Yield", 0.0500)]
        cursor.executemany("INSERT INTO account_types (type_name, interest_rate) VALUES (%s, %s)", account_types)
        conn.commit()
        cursor.execute("SELECT type_id FROM account_types")
        type_ids = [row[0] for row in cursor.fetchall()]

        # 2. Advisors
        advisors_data = [(fake.name(), random.choice(["Wealth Management", "Estate Planning", "Tax Strategy", "Retirement", "Crypto Assets"]), random.randint(50, 200)) for _ in range(10)]
        cursor.executemany("INSERT INTO advisors (full_name, specialization, management_fee_bps) VALUES (%s, %s, %s)", advisors_data)
        conn.commit()
        cursor.execute("SELECT advisor_id FROM advisors")
        advisor_ids = [row[0] for row in cursor.fetchall()]

        # 3. Users
        users_data = [(fake.first_name(), fake.last_name(), fake.unique.email(), fake.phone_number()[:20], fake.date_of_birth(minimum_age=18, maximum_age=90), random.choice(['Conservative', 'Moderate', 'Aggressive'])) for _ in range(100)]
        cursor.executemany("INSERT INTO users (first_name, last_name, email, phone, date_of_birth, risk_profile) VALUES (%s, %s, %s, %s, %s, %s)", users_data)
        conn.commit()
        cursor.execute("SELECT user_id FROM users")
        user_ids = [row[0] for row in cursor.fetchall()]

        # 4. Accounts & Mapping
        for u_id in user_ids:
            if random.random() > 0.3:
                cursor.execute("INSERT INTO advisor_client_mapping (advisor_id, user_id, assignment_date) VALUES (%s, %s, %s)", (random.choice(advisor_ids), u_id, fake.date_this_year()))
            for _ in range(random.randint(1, 3)):
                cursor.execute("INSERT INTO accounts (user_id, account_type_id, balance, currency) VALUES (%s, %s, %s, %s)", (u_id, random.choice(type_ids), round(random.uniform(1000, 500000), 2), "USD"))
        conn.commit()
        cursor.execute("SELECT account_id FROM accounts")
        account_ids = [row[0] for row in cursor.fetchall()]

        # 5. Transactions
        transaction_data = [(acc_id, round(random.uniform(10, 5000), 2), random.choice(['Deposit', 'Withdrawal', 'Transfer', 'Dividend', 'Fee']), fake.sentence(nb_words=5), fake.date_time_this_year()) for acc_id in account_ids for _ in range(random.randint(5, 15))]
        cursor.executemany("INSERT INTO transactions (account_id, amount, category, description, timestamp) VALUES (%s, %s, %s, %s, %s)", transaction_data)
        
        # 6. Portfolio
        tickers = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "NFLX", "BRK.B", "V"]
        holding_data = []
        for acc_id in account_ids:
            if random.random() > 0.4:
                selected_tickers = random.sample(tickers, random.randint(1, 5))
                for ticker in selected_tickers:
                    price = round(random.uniform(50, 3000), 2)
                    holding_data.append((acc_id, ticker, round(random.uniform(1, 100), 4), price, round(price * random.uniform(0.8, 1.3), 2)))
        cursor.executemany("INSERT INTO portfolio_holdings (account_id, ticker_symbol, quantity, purchase_price, current_price) VALUES (%s, %s, %s, %s, %s)", holding_data)
        
        conn.commit()
        print("Data generation complete!")
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
