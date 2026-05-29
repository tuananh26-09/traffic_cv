import mysql.connector

def get_connection():

    return mysql.connector.connect(
        host="mysql",
        user="root",
        password="123456",
        database="traffic_db"
    )

def insert_violation(vehicle_type, speed, violation_type):

    conn = get_connection()

    cursor = conn.cursor()

    query = """
    INSERT INTO violations
    (vehicle_type, speed, violation_type)
    VALUES (%s, %s, %s)
    """

    values = (
        vehicle_type,
        speed,
        violation_type
    )

    cursor.execute(query, values)

    conn.commit()

    cursor.close()
    conn.close()