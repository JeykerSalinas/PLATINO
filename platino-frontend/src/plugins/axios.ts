import axios from "axios";

const axiosInstance = axios.create({
  baseURL: "https://mi.api.com/",
  // Aquí puedes añadir más configuraciones como headers por defecto
});

export default axiosInstance;
