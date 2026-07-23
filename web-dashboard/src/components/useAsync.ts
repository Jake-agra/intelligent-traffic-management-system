import { useCallback, useEffect, useState } from "react";

export interface AsyncResult<T> {
  data: T | null;
  error: unknown;
  isLoading: boolean;
  reload(): void;
}

export function useAsync<T>(loader: () => Promise<T>, deps: React.DependencyList): AsyncResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [version, setVersion] = useState(0);
  const reload = useCallback(() => setVersion((current) => current + 1), []);

  useEffect(() => {
    let disposed = false;
    setIsLoading(true);
    setError(null);
    loader()
      .then((result) => {
        if (!disposed) {
          setData(result);
        }
      })
      .catch((requestError: unknown) => {
        if (!disposed) {
          setError(requestError);
        }
      })
      .finally(() => {
        if (!disposed) {
          setIsLoading(false);
        }
      });
    return () => {
      disposed = true;
    };
  }, [...deps, version]);

  return { data, error, isLoading, reload };
}
