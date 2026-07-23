import type { TokenStore } from "../api/client";

const ACCESS_TOKEN_KEY = "itms.access_token";
const REFRESH_TOKEN_KEY = "itms.refresh_token";

export const sessionTokenStore: TokenStore = {
  getAccessToken() {
    return window.sessionStorage.getItem(ACCESS_TOKEN_KEY);
  },
  getRefreshToken() {
    return window.sessionStorage.getItem(REFRESH_TOKEN_KEY);
  },
  setTokens(accessToken: string, refreshToken: string) {
    window.sessionStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    window.sessionStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  },
  clear() {
    window.sessionStorage.removeItem(ACCESS_TOKEN_KEY);
    window.sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  }
};
