import os
import psycopg2
from psycopg2 import sql
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv() 

app = Flask(__name__)

DB_NAME = "pzemdata"
DB_USER = "pzemuser"
DB_PASSWORD = "pzemsecret"
DB_HOST = "" # Add db url/ip here
DB_PORT = "5432"

""""
DB_NAME = os.getenv("DB_NAME", "pzemdata")
DB_USER = os.getenv("DB_USER", "pzemuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "pzemsecret")
DB_HOST = os.getenv("DB_HOST", "localhost") 
DB_PORT = os.getenv("DB_PORT", "5432")
"""

def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except psycopg2.OperationalError as e:
        app.logger.error(f"Could not connect to database: {e}")
        return None


def create_table_if_not_exists():
    conn = get_db_connection()
    if not conn:
        return
    
    print("Connected to the database! checking/creating table...")
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id SERIAL PRIMARY KEY,
                    reading_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    voltage REAL,
                    current_amps REAL,
                    active_power_watts REAL,
                    active_energy_wh REAL,
                    frequency_hz REAL,
                    power_factor REAL,
                    alarm_status BOOLEAN,
                    device_id VARCHAR(50) DEFAULT 'PZEM004T_01'
                );
            """)
            cur.execute(sql.SQL("GRANT ALL PRIVILEGES ON TABLE sensor_readings TO {};").format(sql.Identifier(DB_USER)))
            cur.execute(sql.SQL("GRANT USAGE, SELECT ON SEQUENCE sensor_readings_id_seq TO {};").format(sql.Identifier(DB_USER)))
            conn.commit()
        app.logger.info("Table 'sensor_readings' checked/created successfully.")
    except Exception as e:
        app.logger.error(f"Error creating/checking table: {e}")
    finally:
        if conn:
            conn.close()

@app.route('/data', methods=['POST'])
def receive_data():
    print("Received data")
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    app.logger.info(f"Received data: {data}")


    required_fields = ["voltage", "current", "power", "energy", "frequency", "powerFactor", "alarmStatus"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        with conn.cursor() as cur:
            query = sql.SQL("""
                INSERT INTO sensor_readings (
                    voltage, current_amps, active_power_watts, active_energy_wh,
                    frequency_hz, power_factor, alarm_status, device_id
                ) VALUES (
                    %(voltage)s, %(current)s, %(power)s, %(energy)s,
                    %(frequency)s, %(powerFactor)s, %(alarmStatus)s, %(deviceId)s
                ) RETURNING id;
            """)

            alarm_status_from_json = data.get("alarmStatus")
            
            if isinstance(alarm_status_from_json, bool):
                db_alarm_status = alarm_status_from_json
            elif isinstance(alarm_status_from_json, str):
                db_alarm_status = alarm_status_from_json.upper() == "ALARM!"
            else:
                db_alarm_status = False

            db_data = {
                "voltage": data.get("voltage"),
                "current": data.get("current"),
                "power": data.get("power"),
                "energy": data.get("energy"),
                "frequency": data.get("frequency"),
                "powerFactor": data.get("powerFactor"),
                "alarmStatus": db_alarm_status,
                "deviceId": data.get("deviceId", "null")
            }
            cur.execute(query, db_data)
            inserted_id = cur.fetchone()[0]
            conn.commit()
        app.logger.info(f"Data inserted with ID: {inserted_id}")
        return jsonify({"message": "Data received and stored", "id": inserted_id}), 201
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error inserting data: {e}")
        return jsonify({"error": f"Failed to store data: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    create_table_if_not_exists() 
    app.run(host='0.0.0.0', port=5000, debug=True)