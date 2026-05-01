import sqlite3
import unittest

from fastapi import HTTPException

from db import seed_role_permissions
from schemas import AdminUserUpdate, AnalysisLabUpdate, AppointmentCreate
from services import admin_service, analyses_service, appointments_service


def make_test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT UNIQUE,
            password_hash TEXT,
            iin TEXT UNIQUE,
            dob TEXT,
            blood_type TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            height REAL,
            weight REAL,
            role TEXT DEFAULT 'user',
            is_active INTEGER DEFAULT 1,
            department TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE role_permissions (
            role TEXT NOT NULL,
            permission TEXT NOT NULL,
            description TEXT,
            PRIMARY KEY (role, permission)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            doctor_user_id INTEGER,
            doctor TEXT,
            speciality TEXT,
            date TEXT,
            time TEXT,
            place TEXT,
            reason TEXT,
            status TEXT DEFAULT 'ожидание',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            doctor_user_id INTEGER,
            name TEXT NOT NULL,
            date TEXT,
            doctor TEXT,
            status TEXT,
            results TEXT,
            ordered_at TEXT,
            scheduled_for TEXT,
            ready_at TEXT,
            reviewed_at TEXT,
            doctor_note TEXT,
            lab_note TEXT,
            is_visible_to_patient INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    seed_role_permissions(cursor)
    cursor.execute(
        "INSERT INTO users (id, name, username, role, is_active, department) VALUES (1, 'Admin', 'admin', 'admin', 1, 'Admin')"
    )
    cursor.execute(
        "INSERT INTO users (id, name, username, role, is_active, department) VALUES (2, 'Doctor', 'doctor', 'doctor', 1, 'Therapy')"
    )
    cursor.execute(
        "INSERT INTO users (id, name, username, role, is_active, department) VALUES (3, 'Patient One', 'patient1', 'user', 1, 'Пациент')"
    )
    cursor.execute(
        "INSERT INTO users (id, name, username, role, is_active, department) VALUES (4, 'Patient Two', 'patient2', 'user', 1, 'Пациент')"
    )
    cursor.execute(
        """
        INSERT INTO appointments (id, user_id, doctor_user_id, doctor, speciality, date, time, status)
        VALUES (1, 3, 2, 'Doctor', 'Therapy', '2099-01-01', '10:00', 'ожидание')
        """
    )
    cursor.execute(
        """
        INSERT INTO analyses (id, user_id, doctor_user_id, name, date, doctor, status, results, is_visible_to_patient)
        VALUES (1, 3, 2, 'CBC', '2099-01-01', 'Doctor', 'назначен', '[]', 1)
        """
    )
    conn.commit()
    return conn


class CoreFlowsTests(unittest.TestCase):
    def setUp(self):
        self.db = make_test_db()
        self.admin = self.db.execute("SELECT * FROM users WHERE id=1").fetchone()
        self.doctor = self.db.execute("SELECT * FROM users WHERE id=2").fetchone()
        self.patient = self.db.execute("SELECT * FROM users WHERE id=3").fetchone()
        self.patient_two = self.db.execute("SELECT * FROM users WHERE id=4").fetchone()

    def tearDown(self):
        self.db.close()

    def test_last_admin_cannot_be_deactivated(self):
        with self.assertRaises(HTTPException) as context:
            admin_service.update_user(
                self.db,
                self.admin,
                1,
                AdminUserUpdate(is_active=False),
            )
        self.assertEqual(context.exception.status_code, 400)

    def test_conflicting_appointment_slot_rejected(self):
        with self.assertRaises(HTTPException) as context:
            appointments_service.create_appointment(
                self.db,
                self.patient,
                AppointmentCreate(
                    user_id=3,
                    doctor_user_id=2,
                    date="2099-01-01",
                    time="10:00",
                    reason="Follow-up",
                ),
            )
        self.assertEqual(context.exception.status_code, 409)

    def test_cancel_appointment_by_patient(self):
        result = appointments_service.cancel_appointment(self.db, self.patient, 1)
        self.assertEqual(result["status"], "cancelled")
        status = self.db.execute("SELECT status FROM appointments WHERE id=1").fetchone()["status"]
        self.assertEqual(status, "отменено")

    def test_doctor_cannot_access_unassigned_patient_analyses(self):
        with self.assertRaises(HTTPException) as context:
            analyses_service.get_user_analyses(self.db, self.doctor, self.patient_two["id"])
        self.assertEqual(context.exception.status_code, 403)

    def test_invalid_analysis_transition_rejected(self):
        with self.assertRaises(HTTPException) as context:
            analyses_service.update_admin_analysis(
                self.db,
                self.admin,
                1,
                AnalysisLabUpdate(status="готово", results=[], ready_at="2099-01-01"),
            )
        self.assertEqual(context.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
