import { FormEvent, useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../components/AuthProvider";

function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { login, register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(email, password);
      }
      navigate("/", { replace: true });
    } catch (err: any) {
      setError(err?.response?.data?.error || "Unable to authenticate.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-surface to-surface-strong px-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-md rounded-2xl border border-border bg-panel/90 p-8 shadow-2xl backdrop-blur"
      >
        <div className="mb-6 space-y-2 text-center">
          <h1 className="text-2xl font-semibold text-foreground">Notion RAG Workspace</h1>
          <p className="text-sm text-muted">
            {mode === "login" ? "Sign in to resume your research." : "Create an account to start exploring."}
          </p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <label className="text-sm font-semibold text-foreground" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-semibold text-foreground" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
              required
              minLength={6}
            />
          </div>
          {error ? <div className="rounded bg-error/10 p-3 text-sm text-error">{error}</div> : null}
          <button
            type="submit"
            className="w-full rounded-lg bg-gradient-to-r from-accent to-indigo-500 px-4 py-2 text-sm font-semibold text-white shadow-lg transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={loading}
          >
            {loading ? "Processing..." : mode === "login" ? "Sign In" : "Create Account"}
          </button>
        </form>
        <p className="mt-6 text-center text-sm text-muted">
          {mode === "login" ? "Need an account?" : "Already have an account?"}{" "}
          <button
            type="button"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
            className="font-semibold text-accent underline-offset-4 transition hover:underline"
          >
            {mode === "login" ? "Register" : "Log in"}
          </button>
        </p>
      </motion.div>
    </div>
  );
}

export default LoginPage;

