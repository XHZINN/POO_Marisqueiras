"""Folha de estilo (QSS) da aplicação.

QSS é tipo o CSS do Qt. Fica tudo aqui pra não ter cor espalhada nas telas.

Detalhe da sintaxe: `::` é sub-elemento (QTabBar::tab) e `:` é estado
(QPushButton:hover).
"""

# Superfícies
FUNDO = "#F6F6F3"
SUPERFICIE = "#FFFFFF"
SUPERFICIE_ALT = "#FAFAF8"
BORDA = "#E5E3DD"
BORDA_FORTE = "#D0CDC5"

# Texto
TEXTO = "#16201F"
TEXTO_SUAVE = "#6B7573"
TEXTO_FRACO = "#9AA3A1"

# Marca
PRIMARIA = "#0C5C58"
PRIMARIA_HOVER = "#0F716C"
PRIMARIA_ESCURA = "#073E3B"
PRIMARIA_SUAVE = "#E7F0EF"

# Estados (RN20 nomeia verde, laranja e vermelho como requisito)
VERDE = "#1F7A33"
VERDE_FUNDO = "#E8F3E9"
LARANJA = "#B45309"
LARANJA_FUNDO = "#FCF0E2"
VERMELHO = "#B3261E"
VERMELHO_FUNDO = "#FBEAE8"

QSS = f"""
QWidget {{
    background-color: {FUNDO};
    color: {TEXTO};
    font-family: "Inter", "Segoe UI", "Ubuntu", "DejaVu Sans", sans-serif;
    font-size: 14px;
}}

/* ---------------- Tipografia ---------------- */

QLabel#marca {{
    font-size: 15px;
    font-weight: 700;
    color: {SUPERFICIE};
    letter-spacing: 1px;
}}
QLabel#titulo {{
    font-size: 30px;
    font-weight: 700;
    color: {TEXTO};
}}
QLabel#subtitulo {{
    font-size: 14px;
    color: {TEXTO_SUAVE};
}}
QLabel#secao {{
    font-size: 12px;
    font-weight: 700;
    color: {TEXTO_FRACO};
    letter-spacing: 1px;
}}
QLabel#nomeEmpresa {{
    font-size: 19px;
    font-weight: 700;
    color: {TEXTO};
}}
QLabel#meta {{
    font-size: 13px;
    color: {TEXTO_SUAVE};
}}
QLabel#metricaValor {{
    font-size: 26px;
    font-weight: 700;
    color: {PRIMARIA};
}}
QLabel#metricaRotulo {{
    font-size: 12px;
    font-weight: 600;
    color: {TEXTO_FRACO};
    letter-spacing: 1px;
}}
QLabel#campoObrigatorio {{
    font-size: 12px;
    font-weight: 600;
    color: {TEXTO_SUAVE};
}}

/* ---------------- Faixa de marca ---------------- */

QFrame#faixa {{
    background-color: {PRIMARIA_ESCURA};
    border: none;
}}
QFrame#faixa QLabel {{
    background-color: transparent;
    color: {SUPERFICIE};
}}
QFrame#faixa QPushButton {{
    background-color: transparent;
    color: #BCD6D4;
    border: 1px solid #2A5F5C;
    padding: 7px 14px;
    font-size: 13px;
}}
QFrame#faixa QPushButton:hover {{
    color: {SUPERFICIE};
    border-color: #4A817E;
}}

/* ---------------- Botões ---------------- */

QPushButton {{
    background-color: {PRIMARIA};
    color: {SUPERFICIE};
    border: none;
    border-radius: 8px;
    padding: 11px 20px;
    font-size: 14px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: {PRIMARIA_HOVER}; }}
QPushButton:pressed {{ background-color: {PRIMARIA_ESCURA}; }}
QPushButton:disabled {{
    background-color: #EDECE8;
    color: {TEXTO_FRACO};
}}

QPushButton#secundario {{
    background-color: {SUPERFICIE};
    color: {TEXTO};
    border: 1px solid {BORDA_FORTE};
}}
QPushButton#secundario:hover {{
    background-color: {SUPERFICIE_ALT};
    border-color: {PRIMARIA};
    color: {PRIMARIA};
}}
QPushButton#secundario:disabled {{
    background-color: {SUPERFICIE};
    border-color: {BORDA};
    color: {TEXTO_FRACO};
}}

QPushButton#sucesso {{ background-color: {VERDE}; }}
QPushButton#sucesso:hover {{ background-color: #196428; }}
QPushButton#sucesso:disabled {{
    background-color: #EDECE8;
    color: {TEXTO_FRACO};
}}

QPushButton#perigo {{
    background-color: {SUPERFICIE};
    color: {VERMELHO};
    border: 1px solid #E8C6C2;
}}
QPushButton#perigo:hover {{ background-color: {VERMELHO_FUNDO}; }}
QPushButton#perigo:disabled {{
    background-color: {SUPERFICIE};
    border-color: {BORDA};
    color: {TEXTO_FRACO};
}}

/* ---------------- Campos ---------------- */

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {{
    background-color: {SUPERFICIE};
    border: 1px solid {BORDA_FORTE};
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 14px;
    selection-background-color: {PRIMARIA};
    selection-color: {SUPERFICIE};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QTextEdit:focus {{
    border: 1px solid {PRIMARIA};
}}

QComboBox::drop-down {{
    border: none;
    width: 26px;
}}
QComboBox QAbstractItemView {{
    background-color: {SUPERFICIE};
    border: 1px solid {BORDA_FORTE};
    border-radius: 8px;
    padding: 4px;
    outline: none;
    selection-background-color: {PRIMARIA_SUAVE};
    selection-color: {TEXTO};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 18px;
    border: none;
    background: transparent;
}}

/* ---------------- Tabelas ---------------- */

QTableWidget {{
    background-color: {SUPERFICIE};
    border: 1px solid {BORDA};
    border-radius: 10px;
    gridline-color: transparent;
    outline: none;
    selection-background-color: {PRIMARIA_SUAVE};
    selection-color: {TEXTO};
}}
QTableWidget::item {{
    padding: 0px 12px;
    border: none;
    border-bottom: 1px solid #F1EFEA;
}}
QTableWidget::item:selected {{
    background-color: {PRIMARIA_SUAVE};
    color: {TEXTO};
}}
QHeaderView {{ background-color: transparent; }}
QHeaderView::section {{
    background-color: {SUPERFICIE_ALT};
    color: {TEXTO_FRACO};
    padding: 12px;
    border: none;
    border-bottom: 1px solid {BORDA};
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.5px;
}}
QTableCornerButton::section {{
    background-color: {SUPERFICIE_ALT};
    border: none;
}}

/* ---------------- Abas ---------------- */

QTabWidget::pane {{
    border: none;
    background-color: transparent;
    top: 0px;
}}
QTabBar {{ qproperty-drawBase: 0; }}
QTabBar::tab {{
    background: transparent;
    color: {TEXTO_SUAVE};
    padding: 12px 2px;
    margin-right: 28px;
    font-size: 14px;
    font-weight: 600;
    border: none;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:hover {{ color: {TEXTO}; }}
QTabBar::tab:selected {{
    color: {PRIMARIA};
    border-bottom: 2px solid {PRIMARIA};
}}

/* ---------------- Cartões ---------------- */

QFrame#cartao {{
    background-color: {SUPERFICIE};
    border: 1px solid {BORDA};
    border-radius: 12px;
}}
QFrame#cartao QLabel {{ background-color: transparent; }}

QFrame#divisor {{
    background-color: {BORDA};
    border: none;
    max-height: 1px;
}}

QGroupBox {{
    background-color: {SUPERFICIE};
    border: 1px solid {BORDA};
    border-radius: 12px;
    margin-top: 10px;
    padding: 22px 18px 18px 18px;
    font-size: 12px;
    font-weight: 700;
    color: {TEXTO_FRACO};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 18px;
    top: 2px;
    padding: 0;
    letter-spacing: 1px;
}}
QGroupBox QLabel {{ background-color: transparent; }}

/* ---------------- Listas ---------------- */

QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{
    background-color: {SUPERFICIE};
    color: {TEXTO};
    border: 1px solid {BORDA};
    border-radius: 12px;
    margin-bottom: 10px;
}}
QListWidget::item:hover {{ border-color: {BORDA_FORTE}; }}
/* O `color` aqui não é enfeite: sem ele o item selecionado herda o branco
   do tema e o texto some no fundo claro do cartão. */
QListWidget::item:selected {{
    border: 2px solid {PRIMARIA};
    background-color: {SUPERFICIE};
    color: {TEXTO};
}}

QListWidget#carrinho::item {{
    background-color: {SUPERFICIE_ALT};
    border: 1px solid {BORDA};
    border-radius: 8px;
    margin-bottom: 6px;
    padding: 11px 13px;
    font-size: 13px;
}}
QListWidget#carrinho::item:selected {{
    background-color: {PRIMARIA_SUAVE};
    border: 1px solid {PRIMARIA};
    color: {TEXTO};
}}

/* ---------------- Barras de rolagem ---------------- */

QScrollBar:vertical {{
    background: transparent;
    width: 11px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #CFD4D2;
    border-radius: 5px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{ background: #B4BBB9; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 11px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: #CFD4D2;
    border-radius: 5px;
    min-width: 32px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---------------- Diálogos ---------------- */

QDialog {{ background-color: {FUNDO}; }}
QMessageBox {{ background-color: {SUPERFICIE}; }}
QMessageBox QLabel {{ background-color: transparent; }}
QMessageBox QPushButton {{ min-width: 84px; }}
QInputDialog {{ background-color: {SUPERFICIE}; }}
QInputDialog QLabel {{ background-color: transparent; }}

QToolTip {{
    background-color: {TEXTO};
    color: {SUPERFICIE};
    border: none;
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 13px;
}}
"""
