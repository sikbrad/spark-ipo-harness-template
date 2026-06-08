#!/usr/bin/env node
import fs from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';

const portalRoot = '/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az';
const requireFromPortal = createRequire(path.join(portalRoot, 'package.json'));
const { Client } = requireFromPortal('pg');

function readEnv(file) {
  const env = {};
  for (const rawLine of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#') || !line.includes('=')) continue;
    const idx = line.indexOf('=');
    env[line.slice(0, idx)] = line.slice(idx + 1).replace(/^['"]|['"]$/g, '');
  }
  return env;
}

const env = readEnv(path.join(portalRoot, '.env'));
const client = new Client({ connectionString: env.DATABASE_URL });

const sql = `
WITH customer_agg AS (
  SELECT
    "companyUk",
    jsonb_agg(jsonb_build_object(
      'id', id,
      'uk', uk,
      'name', name,
      'email', email,
      'phone', phone,
      'officePhone', "officePhone",
      'isKeyMan', "isKeyMan"
    ) ORDER BY "isKeyMan" DESC, id ASC) AS customers
  FROM "Customer"
  WHERE "deletedAt" IS NULL
  GROUP BY "companyUk"
),
shipping_agg AS (
  SELECT
    "companyUk",
    jsonb_agg(jsonb_build_object(
      'id', id,
      'address', address,
      'addressDetail', "addressDetail",
      'zipCode', "zipCode",
      'isDefault', "isDefault",
      'latestOrderName', "latestOrderName",
      'latestShippingDate', "latestShippingDate"
    ) ORDER BY "isDefault" DESC, id ASC) AS shipping_addresses
  FROM "CompanyShippingAddress"
  WHERE "deletedAt" IS NULL
  GROUP BY "companyUk"
),
order_stats AS (
  SELECT
    "companyUk",
    count(*)::int AS orders_count,
    max("createdAt") AS latest_order_created_at,
    max("orderDate") AS latest_order_date
  FROM "Order"
  WHERE "deletedAt" IS NULL
  GROUP BY "companyUk"
),
recent_order AS (
  SELECT DISTINCT ON ("companyUk")
    "companyUk",
    "orderNo",
    "orderName",
    "orderDate",
    status::text AS order_status,
    "createdAt",
    phone,
    "shippingAddress"
  FROM "Order"
  WHERE "deletedAt" IS NULL
  ORDER BY "companyUk", "createdAt" DESC
),
product_agg AS (
  SELECT
    o."companyUk",
    jsonb_agg(DISTINCT p."productName") FILTER (WHERE p."productName" IS NOT NULL) AS product_names
  FROM "Order" o
  JOIN "OrderProduct" p ON p."orderUk" = o.uk
  WHERE o."deletedAt" IS NULL
  GROUP BY o."companyUk"
),
contract_stats AS (
  SELECT
    "companyUk",
    count(*)::int AS contracts_count
  FROM "Contract"
  WHERE "deletedAt" IS NULL
  GROUP BY "companyUk"
)
SELECT
  c.id,
  c.uk,
  c.name,
  c."businessName",
  c.type::text AS type,
  c.country,
  c.currency::text AS currency,
  c.status::text AS status,
  c."erpId",
  c.email,
  c.email2,
  c.phone,
  c.mobile1,
  c.mobile2,
  c.website,
  c."zipCode",
  c.address,
  c."addressDetail",
  c."createdAt",
  c."updatedAt",
  coalesce(customer_agg.customers, '[]'::jsonb) AS customers,
  coalesce(shipping_agg.shipping_addresses, '[]'::jsonb) AS shipping_addresses,
  coalesce(order_stats.orders_count, 0) AS orders_count,
  order_stats.latest_order_created_at,
  order_stats.latest_order_date,
  jsonb_build_object(
    'orderNo', recent_order."orderNo",
    'orderName', recent_order."orderName",
    'orderDate', recent_order."orderDate",
    'status', recent_order.order_status,
    'createdAt', recent_order."createdAt",
    'phone', recent_order.phone,
    'shippingAddress', recent_order."shippingAddress"
  ) AS latest_order,
  coalesce(product_agg.product_names, '[]'::jsonb) AS product_names,
  coalesce(contract_stats.contracts_count, 0) AS contracts_count
FROM "Company" c
LEFT JOIN customer_agg ON customer_agg."companyUk" = c.uk
LEFT JOIN shipping_agg ON shipping_agg."companyUk" = c.uk
LEFT JOIN order_stats ON order_stats."companyUk" = c.uk
LEFT JOIN recent_order ON recent_order."companyUk" = c.uk
LEFT JOIN product_agg ON product_agg."companyUk" = c.uk
LEFT JOIN contract_stats ON contract_stats."companyUk" = c.uk
WHERE c."deletedAt" IS NULL
ORDER BY c.id ASC
`;

try {
  await client.connect();
  const result = await client.query(sql);
  process.stdout.write(JSON.stringify(result.rows));
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
} finally {
  await client.end().catch(() => {});
}
