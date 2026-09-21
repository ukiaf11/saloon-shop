import { SelectionCart } from "@/components/cart/selection-cart";
import { Footer } from "@/components/layout/footer";
import { Navbar } from "@/components/layout/navbar";
import { CartProvider } from "@/lib/cart";
import { SALON_NAME } from "@/lib/site";

export default function SiteLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // The provider wraps the whole site so a service card anywhere on the page
    // can add to the same cart the sticky bar reads. Server Components stay
    // server-rendered: only the islands are client.
    <CartProvider>
      <Navbar salonName={SALON_NAME} />
      <main id="main">{children}</main>
      <Footer salonName={SALON_NAME} />
      <SelectionCart />
    </CartProvider>
  );
}
