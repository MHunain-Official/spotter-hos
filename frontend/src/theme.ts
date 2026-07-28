import { createTheme } from "@mui/material/styles";

/** Light freight-ops theme — ink navy + signal coral (not dark amber SaaS). */
const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#E23D28", contrastText: "#FFFFFF" },
    secondary: { main: "#0B1F33", contrastText: "#FFFFFF" },
    success: { main: "#1F7A4C" },
    warning: { main: "#C45C12" },
    info: { main: "#1A5F7A" },
    background: {
      default: "#E9EEF2",
      paper: "#FFFFFF",
    },
    text: {
      primary: "#0B1F33",
      secondary: "#4A5B6A",
    },
    divider: "rgba(11,31,51,0.12)",
  },
  typography: {
    fontFamily: '"Manrope", "Segoe UI", sans-serif',
    h1: {
      fontFamily: '"Syne", sans-serif',
      fontWeight: 800,
      letterSpacing: "-0.04em",
    },
    h2: {
      fontFamily: '"Syne", sans-serif',
      fontWeight: 700,
      letterSpacing: "-0.03em",
    },
    h3: {
      fontFamily: '"Syne", sans-serif',
      fontWeight: 700,
      letterSpacing: "-0.02em",
    },
    h5: {
      fontFamily: '"Syne", sans-serif',
      fontWeight: 700,
    },
    button: { textTransform: "none", fontWeight: 700 },
    overline: {
      fontFamily: '"Manrope", sans-serif',
      letterSpacing: "0.16em",
      fontWeight: 700,
    },
  },
  shape: { borderRadius: 4 },
  components: {
    MuiButton: {
      styleOverrides: {
        root: { borderRadius: 4, paddingInline: 20, boxShadow: "none" },
        contained: {
          "&:hover": { boxShadow: "none" },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: "none" },
      },
    },
    MuiTextField: {
      defaultProps: { variant: "outlined", size: "medium" },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          backgroundColor: "#fff",
          borderRadius: 4,
        },
      },
    },
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: "#E9EEF2",
        },
      },
    },
  },
});

export default theme;
