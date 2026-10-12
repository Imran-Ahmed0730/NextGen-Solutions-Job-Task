import type { Metadata } from 'next';
import 'sweetalert2/dist/sweetalert2.min.css';
import './globals.css';

export const metadata: Metadata = {
  title: 'Sabuj Pran Business Suite',
  description: 'Role-secured business management workspace',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
