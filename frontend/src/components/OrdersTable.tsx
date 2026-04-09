import type { Document, Order } from "../types/api";

type Props = {
  orders: Order[];
  documents: Document[];
  onViewDocument: (documentId: number, name?: string | null) => void;
};

export function OrdersTable({ orders, documents, onViewDocument }: Props) {
  const docsByOrder = documents.reduce<Record<string, Document[]>>((acc, doc) => {
    if (!acc[doc.order_id]) {
      acc[doc.order_id] = [];
    }
    acc[doc.order_id].push(doc);
    return acc;
  }, {});

  if (orders.length === 0) {
    return <p className="hint">No orders for this patient.</p>;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Order ID</th>
            <th>Type</th>
            <th>Status</th>
            <th>Documents</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => {
            const linkedDocs = docsByOrder[order.order_id] ?? [];
            return (
              <tr key={order.id}>
                <td className="order-id-cell">{order.order_id}</td>
                <td>{order.doc_type ?? "--"}</td>
                <td>
                  <span className="table-status">{order.status ?? "--"}</span>
                </td>
                <td>
                  {linkedDocs.length === 0 ? (
                    "--"
                  ) : (
                    <div className="doc-actions">
                      {linkedDocs.map((doc) => (
                        <button
                          key={doc.id}
                          className="mini-btn"
                          onClick={() => onViewDocument(doc.id, doc.filename)}
                          title={doc.filename ?? `Document ${doc.id}`}
                        >
                          View
                        </button>
                      ))}
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}