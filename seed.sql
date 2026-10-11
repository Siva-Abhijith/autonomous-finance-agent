INSERT INTO invoices (invoice_number, vendor, amount, due_date)
VALUES
    ('DEMO-1001', 'Acme Supplies', 12500.00, '2026-11-15'),
    ('DEMO-1002', 'Acme Supplies', 18750.00, '2026-12-01'),
    ('DEMO-1003', 'Northstar Office Products', 9200.00, '2026-11-20'),
    ('DEMO-1004', 'Greenfield Packaging', 24300.00, '2026-12-10')
ON CONFLICT (invoice_number) DO NOTHING;
