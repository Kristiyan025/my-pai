import { useRouter } from "next/router";
import Head from "next/head";
import { useEffect } from "react";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to chat page by default
    router.push("/chat");
  }, [router]);

  return (
    <>
      <Head>
        <title>My PAI - Personal AI Assistant</title>
      </Head>
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-xl">Loading...</div>
      </div>
    </>
  );
}
