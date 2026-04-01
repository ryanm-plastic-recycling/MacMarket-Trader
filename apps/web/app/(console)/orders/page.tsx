"use client";
import { useEffect, useState } from "react";

type Order = { order_id: string; symbol: string; status: string; side: string; shares: number; limit_price: number; created_at: string; fills: Array<{ fill_price: number; timestamp: string }> };

export default function Page() {
  const [orders, setOrders] = useState<Order[]>([]);
  useEffect(() => { fetch("/api/user/orders", { cache: "no-store" }).then((r) => r.json()).then(setOrders); }, []);
  return <section><h1>Orders</h1><table><thead><tr><th>order</th><th>status</th><th>side</th><th>shares</th><th>limit</th><th>fill</th><th>timestamps</th></tr></thead>
    <tbody>{orders.map((o) => <tr key={o.order_id}><td>{o.symbol}</td><td>{o.status}</td><td>{o.side}</td><td>{o.shares}</td><td>{o.limit_price}</td><td>{o.fills[0]?.fill_price ?? "-"}</td><td>{o.created_at} / {o.fills[0]?.timestamp ?? "-"}</td></tr>)}</tbody></table></section>;
}
