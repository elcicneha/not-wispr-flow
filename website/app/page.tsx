import Header from "@/components/sections/Header";
import Hero from "@/components/sections/Hero";
import Marquee from "@/components/sections/Marquee";
import DemoSection from "@/components/sections/DemoSection";
import Features from "@/components/sections/Features";
import Install from "@/components/sections/Install";
import Asterisks from "@/components/ui/Asterisks";
import Footer from "@/components/sections/Footer";
import { marqueeItems } from "@/lib/content";

export default function Home() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <Marquee items={marqueeItems} />
        <DemoSection />
        <Features />
        <Install />
        <Asterisks />
        <Footer />
      </main>
    </>
  );
}
