import axios from "axios";
import { useNotificationStore } from "@/stores/notifications";
const apiUrl = import.meta.env.VITE_API_URL;
const axiosInstance = axios.create({
  baseURL: apiUrl,
  // Aquí puedes añadir más configuraciones como headers por defecto
});

export function setupAxiosInterceptors() {
  axiosInstance.interceptors.response.use(
    (response) => response,
    (error) => {
      const store = useNotificationStore();
      const msg = error.response?.data?.detail || error.message;
      store.notify(msg, "error");
      return Promise.reject(error);
    }
  );
}

export default axiosInstance;
