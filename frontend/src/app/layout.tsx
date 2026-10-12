import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Sabuj Pran Business Suite',
  description: 'Business management dashboard foundation',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
