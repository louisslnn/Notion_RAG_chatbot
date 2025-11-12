import { Navigate } from "react-router-dom";
import { ReactNode } from "react";
import { useAuth } from "./AuthProvider";

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface">
        <div className="animate-pulse rounded-lg bg-panel px-6 py-4 shadow-md">
          Loading workspace...
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/auth" replace />;
  }

  return <>{children}</>;
}

export default ProtectedRoute;

