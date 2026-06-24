import csv
import io
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPENSES_FILE = os.path.join(BASE_DIR, "expenses.json")
CATEGORIES_FILE = os.path.join(BASE_DIR, "categories.json")
INDEX_FILE = os.path.join(BASE_DIR, "templates", "index.html")
DEFAULT_CATEGORIES = ["Casa", "Obras"]


def load_json(path, default):
    if not os.path.exists(path):
        save_json(path, default)
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_expenses():
    return load_json(EXPENSES_FILE, [])


def save_expenses(expenses):
    save_json(EXPENSES_FILE, expenses)


def load_categories():
    return load_json(CATEGORIES_FILE, list(DEFAULT_CATEGORIES))


def save_categories(categories):
    save_json(CATEGORIES_FILE, categories)


class Handler(BaseHTTPRequestHandler):
    server_version = "ExpensesTracker/1.0"

    def log_message(self, fmt, *args):
        pass

    # ── helpers ──────────────────────────────────────
    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message, status=400):
        self.send_json({"error": message}, status)

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def send_html(self, path):
        try:
            with open(path, "rb") as f:
                body = f.read()
        except FileNotFoundError:
            self.send_error_json("Página não encontrada.", 404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_csv(self, content_bytes, filename):
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(content_bytes)))
        self.end_headers()
        self.wfile.write(content_bytes)

    # ── routing ──────────────────────────────────────
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/":
            self.send_html(INDEX_FILE)
        elif path == "/api/expenses":
            self.handle_get_expenses(qs)
        elif path == "/api/categories":
            self.send_json(load_categories())
        elif path == "/api/export/csv":
            self.handle_export_csv(qs)
        else:
            self.send_error_json("Não encontrado.", 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/expenses":
            self.handle_add_expense()
        elif path == "/api/categories":
            self.handle_add_category()
        else:
            self.send_error_json("Não encontrado.", 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/expenses/"):
            expense_id = path[len("/api/expenses/"):]
            self.handle_delete_expense(expense_id)
        else:
            self.send_error_json("Não encontrado.", 404)

    # ── handlers ─────────────────────────────────────
    def handle_get_expenses(self, qs):
        category = (qs.get("category") or [None])[0]
        expenses = load_expenses()
        if category:
            expenses = [e for e in expenses if category in e.get("categories", [])]
        expenses.sort(key=lambda e: (e.get("date", ""), e.get("time", "")), reverse=True)
        self.send_json(expenses)

    def handle_add_expense(self):
        data = self.read_json_body()
        title = (data.get("title") or "").strip()
        amount = data.get("amount")

        if not title:
            self.send_error_json("Título é obrigatório.", 400)
            return
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            self.send_error_json("Valor inválido.", 400)
            return

        expense = {
            "id": str(int(time.time() * 1000)),
            "title": title,
            "description": (data.get("description") or "").strip(),
            "date": data.get("date") or "",
            "time": data.get("time") or "",
            "amount": amount,
            "categories": data.get("categories") or [],
        }

        expenses = load_expenses()
        expenses.append(expense)
        save_expenses(expenses)
        self.send_json(expense, 201)

    def handle_delete_expense(self, expense_id):
        expenses = load_expenses()
        remaining = [e for e in expenses if e.get("id") != expense_id]
        if len(remaining) == len(expenses):
            self.send_error_json("Despesa não encontrada.", 404)
            return
        save_expenses(remaining)
        self.send_json({"ok": True})

    def handle_add_category(self):
        data = self.read_json_body()
        name = (data.get("name") or "").strip()
        if not name:
            self.send_error_json("Nome da categoria é obrigatório.", 400)
            return

        categories = load_categories()
        if name not in categories:
            categories.append(name)
            save_categories(categories)
        self.send_json(categories, 201)

    def handle_export_csv(self, qs):
        category = (qs.get("category") or [None])[0]
        expenses = load_expenses()
        if category:
            expenses = [e for e in expenses if category in e.get("categories", [])]
        expenses.sort(key=lambda e: (e.get("date", ""), e.get("time", "")), reverse=True)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Data", "Hora", "Título", "Descrição", "Valor (€)", "Categorias"])
        for e in expenses:
            writer.writerow([
                e.get("date", ""),
                e.get("time", ""),
                e.get("title", ""),
                e.get("description", ""),
                f"{e.get('amount', 0):.2f}",
                ", ".join(e.get("categories", [])),
            ])

        csv_bytes = ("﻿" + output.getvalue()).encode("utf-8")
        filename = "despesas.csv" if not category else f"despesas_{category}.csv"
        self.send_csv(csv_bytes, filename)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 8020), Handler)
    print("A correr em http://0.0.0.0:8020")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
