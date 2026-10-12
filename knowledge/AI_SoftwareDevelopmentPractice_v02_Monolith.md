Time Line:

Start date: 12/10/2026

End date: 17/10/2026 Before 11:59 PM

BUSINESS MANAGEMENT SOFTWARE

Software Development Plan & Technical Implementation
Blueprint

1. PURPOSE OF THIS DOCUMENT

The Business Requirements document explains what customer’s needs.

This document explains:

  how the system should be divided into software modules
  approximately how many frontend screens are required
  how many dashboards are required
  what reports should be developed
  what database tables are required
  what database views are required
  whether stored procedures/functions/triggers are needed
  how APIs should be organized
  how development should be phased
  what should be tested
  how AI tools such as ChatGPT, Codex, Claude Code, Gemini, Cursor or similar

tools should be used

  how to prevent AI-generated code from becoming inconsistent or unreliable

This should become the main implementation planning document.

Address: Taruchaya, First floor, Plot – L/7, Block – L, Eastern Housing – Extension, Pallabi, Mirpur, Dhaka – 1216
Contact No: +8801726621896 Email: info@nextgenitltd.com  Website: www.nextgenitltd.com

2. RECOMMENDED ARCHITECTURE

For Sabuj Pran, the recommended architecture is a:

MODULAR MONOLITH

This  means  one  main  application,  but  divided  internally  into  clear  modules.  This  is
preferable to microservices for an initial 10–20 employee company. The system can later
be divided into services if necessary.

Major modules:

1.  Authentication & Users
2.  Company Setup
3.  Products & Pricing
4.  Customers
5.  Suppliers
6.  Sales
7.  Purchase
8.  Inventory
9.  Production
10. Money & Simple Accounting
11. Assets
12. Employees
13. Approvals
14. Reports
15. Audit & Administration

3. HIGH-LEVEL APPLICATION STRUCTURE

Address: Taruchaya, First floor, Plot – L/7, Block – L, Eastern Housing – Extension, Pallabi, Mirpur, Dhaka – 1216
Contact No: +8801726621896 Email: info@nextgenitltd.com  Website: www.nextgenitltd.com

4. RECOMMENDED FRONTEND TECHNOLOGY

Recommended:

  Next.js
  React


TypeScript

Suggested frontend supporting libraries:

Zod
Tailwind CSS or equivalent

  React Query / TanStack Query
  React Hook Form


  Component Library
  Charting Library
  Date Library
  PDF/Print Utilities

Business logic should remain primarily in FastAPI.

The frontend should focus on:

  data entry
  display
  validation feedback
  workflow
  usability

5. SCREEN SUMMARY

Area

Estimated Screens

Login & Profile

Dashboard

Master Data & Setup

Customer & Supplier

Sales

Purchase

Inventory

Employee

Administration & Control

4

1

8

4

5

3

2

3

8

38

Total

Address: Taruchaya, First floor, Plot – L/7, Block – L, Eastern Housing – Extension, Pallabi, Mirpur, Dhaka – 1216
Contact No: +8801726621896 Email: info@nextgenitltd.com  Website: www.nextgenitltd.com

6. LOGIN & PROFILE SCREENS — 4

6.1 Login

Purpose:

Allow authorized employees to access the system.

Functions:

  username/email/mobile
  password
login


  session management

6.2 Forgot Password

Purpose:

Recover/reset user access.

6.3 My Profile

Purpose:

User can see/update permitted personal information.

6.4 Change Password

Purpose:

Secure password management.

7. DASHBOARDS — 1

Dashboards should be role-based.

7.1 Owner / Management Dashboard

Shows:

  Today's Sales

Address: Taruchaya, First floor, Plot – L/7, Block – L, Eastern Housing – Extension, Pallabi, Mirpur, Dhaka – 1216
Contact No: +8801726621896 Email: info@nextgenitltd.com  Website: www.nextgenitltd.com

  Today's Collection
  Today's Expenses
  Today's Purchase
  Cash
  Bank
  MFS balances
  Customer Due
  Supplier Due


Inventory Value
  Pending Orders
  Estimated Profit

8. MASTER DATA & SETUP SCREENS — 8

8.1 Product List

Search/view products.

8.2 Product Categories

Maintain product classifications.

8.3 Units of Measurement

KG, Piece, Roll, Block, etc.

8.4 Product Price List

Maintain sales prices.

8.5 Expense Categories

Configure expense types.

8.6 Income Categories

Configure income types.

8.7 Payment Methods

Cash, Bank, MFS, online, etc.

Address: Taruchaya, First floor, Plot – L/7, Block – L, Eastern Housing – Extension, Pallabi, Mirpur, Dhaka – 1216
Contact No: +8801726621896 Email: info@nextgenitltd.com  Website: www.nextgenitltd.com

8.8 Company Settings

Company information, currency, timezone, invoice settings, etc.

9. CUSTOMER & SUPPLIER SCREENS — 4

Customers

9.1 Customer List

9.2 Customer Add/Edit

Suppliers

9.5 Supplier List

9.6 Supplier Add/Edit

10. SALES SCREENS — 5

10.1 Quotation List

10.2 Create/Edit Quotation

10.3 Sales Order List

10.4 Create/Edit Sales Order

10.5 Sales Order Details

Shows:

  Ordered
  Available
  Reserved
  Produced
  Delivered
  Remaining

Address: Taruchaya, First floor, Plot – L/7, Block – L, Eastern Housing – Extension, Pallabi, Mirpur, Dhaka – 1216
Contact No: +8801726621896 Email: info@nextgenitltd.com  Website: www.nextgenitltd.com

11. PURCHASE SCREENS — 3

11.1 Purchase Order List

11.2 Create/Edit Purchase Order

11.3 Purchase Order Details

12. INVENTORY SCREENS — 2

12.1 Current Stock

Search/filter all products.

12.2 Product Stock Ledger

Shows complete movement history.

13. EMPLOYEE SCREENS — 3

Employees

13.1 Employee List

13.2 Employee Add/Edit

13.3 Attendance / Basic Payroll

Can be simplified initially.

14. ADMINISTRATION & CONTROL SCREENS — 8

14.1 User List

14.2 User Add/Edit

14.3 Roles

14.4 Permissions

14.5 Approval Rules

Address: Taruchaya, First floor, Plot – L/7, Block – L, Eastern Housing – Extension, Pallabi, Mirpur, Dhaka – 1216
Contact No: +8801726621896 Email: info@nextgenitltd.com  Website: www.nextgenitltd.com

14.6 Pending Approvals

14.7 Audit Log

14.8 Document Numbering / System Configuration

15. DEVELOPMENT PHASES

PHASE 0 — PROJECT FOUNDATION

Build:



repositories

  backend structure
frontend structure


  Docker
  environment configuration
  MySQL
  migration system
testing framework

  coding conventions
  CI/CD foundation

Deliverable:

Empty but correctly structured working application.

PHASE 1 — AUTHENTICATION & SECURITY

Build:



login
  users
roles


  permissions
  profile
  password handling
  audit foundation

Do not proceed until access control works.

Address: Taruchaya, First floor, Plot – L/7, Block – L, Eastern Housing – Extension, Pallabi, Mirpur, Dhaka – 1216
Contact No: +8801726621896 Email: info@nextgenitltd.com  Website: www.nextgenitltd.com

PHASE 2 — MASTER DATA

Build:

  Product
  Categories
  Units
  Warehouses
  Prices
  Expense Categories
Income Categories

  Payment Methods
  Money Accounts

This becomes the foundation for later transactions.

PHASE 3 — CUSTOMERS & SUPPLIERS

Build:

  customer master
  supplier master
  opening dues
  statements
  contact information

PHASE 4 — INVENTORY ENGINE

This should be developed before sales and production.

Build:

  Stock Transaction
  Stock Balance
  Warehouse Stock
  Transfer
  Adjustment
  Physical Count
  Stock Ledger

This is one of the most critical phases.

Address: Taruchaya, First floor, Plot – L/7, Block – L, Eastern Housing – Extension, Pallabi, Mirpur, Dhaka – 1216
Contact No: +8801726621896 Email: info@nextgenitltd.com  Website: www.nextgenitltd.com

PHASE 5 — PURCHASE

Build:

  Purchase Order
  Goods Receive
  Direct Purchase
  Supplier Due
  Purchase Return

Test that purchase correctly updates inventory.

PHASE 6 — SIMPLE MONEY SYSTEM

Build:

  Cash
  Bank
  bKash/Nagad
  Expense
Income


  Customer Collection
  Supplier Payment
  Transfer
  Opening Balance

This provides financial visibility early.

PHASE 7 — SALES

Build:

  Quotation
  Sales Order
  Reservation
  Delivery
Invoice

  Sales Return
  Customer Due

Test stock and customer balance together.

Address: Taruchaya, First floor, Plot – L/7, Block – L, Eastern Housing – Extension, Pallabi, Mirpur, Dhaka – 1216
Contact No: +8801726621896 Email: info@nextgenitltd.com  Website: www.nextgenitltd.com

THE REQUIREMENT WINS.

AI is the development assistant. It is not the owner of the business rules.

16. PROJECT SUCCESS CRITERIA

The software project is successful when it can reliably run the complete business cycle:

Supplier
↓
Raw Material Purchase
↓
Stock
↓
Sale
↓
Customer Due
↓
Customer Collection
↓
Cash / Bank / MFS
↓
Expense
↓
Management Dashboard

and management can obtain reliable answers about:

  stock
  orders
  sales
  purchase
  customer due
  supplier due
  cash
  bank
  mobile banking
  expenses
  profit

This document should therefore be treated as the technical implementation roadmap
as Business Requirements Specification.

Address: Taruchaya, First floor, Plot – L/7, Block – L, Eastern Housing – Extension, Pallabi, Mirpur, Dhaka – 1216
Contact No: +8801726621896 Email: info@nextgenitltd.com  Website: www.nextgenitltd.com

