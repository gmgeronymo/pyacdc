#!/usr/bin/env python

from PyQt5.QtCore import QDir, Qt
from PyQt5.QtWidgets import (QApplication, QCheckBox, QFileDialog, QGridLayout,
        QGroupBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSpinBox,
        QVBoxLayout, QWidget, QComboBox, QLineEdit)
import visa
from abc import ABCMeta, abstractmethod

# Constantes e variáveis globais
# comandos da chave (em ASCII puro)
reset = chr(2)
ac = chr(4)
dc = chr(6)

def espera(segundos):
    for i in range(int(segundos * 10)):
        time.sleep(0.1)    
    return

class Instrumento(object):
    """ Classe genérica para os instrumentos
    Atributos:
    barramento: numero do barramento GPIB utilizado
    endereco: string com o endereço GPIB do instrumento
    modelo: modelo do instrumento
    """

    __metaclass__ = ABCMeta
    def __init__(self, bus, endereco, modelo):
        self.endereco = endereco
        self.bus = bus
        self.gpib = rm.open_resource("GPIB"+self.bus+"::"+self.endereco+"::INSTR")
        self.modelo = modelo

    def close(self):
        self.gpib.close()
        return
#-------------------------------------------------------------------------------
        
class Chave(Instrumento):
    """ Classe para a chave AC-DC
    Atributos:
    endereco: string com o endereço GPIB do instrumento
    modelo: modelo do instrumento ('METAS')
    """

    def __init__(self,bus,endereco):
        Instrumento.__init__(self, bus, endereco,'METAS')
    
    def print_idn(self):
        print("Comunicando com a chave no endereço "+self.endereco+".");
        print("reset");
        self.gpib.write_raw(reset);
        print("\n\n");
        return

#-------------------------------------------------------------------------------
    
class Fonte(Instrumento):
    """ Classe para as fontes AC e DC
    Atributos:
    endereco: string com o endereço GPIB do instrumento
    modelo: modelo do instrumento ('5700A', '5720A', '5730A', etc.)
    tipo: string, assume os valores 'AC' ou 'DC'
    """
    def __init__(self, bus, endereco, modelo, tipo):
        Instrumento.__init__(self, bus, endereco, modelo)
        if (tipo != 'AC') & (tipo != 'DC'):
            raise NameError('tipo deve ser AC ou DC')
        
        self.tipo = tipo
        self.idn = self.gpib.query("*IDN?");

    def print_idn(self):
        print("Comunicando com fonte "+self.tipo+" no endereço "+self.endereco+".")
        print("String de identificação: ")
        print(self.idn)
        print("\n\n")
        return

#-------------------------------------------------------------------------------
    
class Medidor(Instrumento):
    """ Classe para as medidores do padrão e do objeto
    Atributos:
    endereco: string com o endereço GPIB do instrumento
    modelo: modelo do instrumento ('182A', '2182A', '53181A', '3458A', etc.)
    tipo: string, assume os valores 'STD' ou 'DUT'
    """
    def __init__(self, tipo):
        Instrumento.__init__(self, config['GPIB'][tipo], config['Instruments'][tipo])
        if (tipo != 'DUT') & (tipo != 'STD'):
            raise NameError('tipo deve ser STD ou DUT')

        self.tipo = tipo

        if self.modelo == '3458A':
            self.gpib.write("OFORMAT ASCII")
            self.gpib.write("END ALWAYS")
            self.gpib.write("NPLC 8")
            self.idn = self.gpib.query("ID?");
            
        elif self.modelo == '182A':
            self.gpib.write("R0I0B1X")
            self.gpib.write("S2N1X")
            self.gpib.write("O1P2X")
            self.idn = "Keithley 182A"

        elif self.modelo == '53132A':
            self.idn = self.gpib.query("*IDN?");
            self.gpib.write("*RST")
            self.gpib.write("*CLS")
            self.gpib.write("*SRE 0")
            self.gpib.write("*ESE 0")
            self.gpib.write(":STAT:PRES")
            # comandos para throughput máximo
            self.gpib.write(":FORMAT ASCII")
            self.gpib.write(":FUNC 'FREQ 1'")
            self.gpib.write(":EVENT1:LEVEL 0")
            # configura o gate size (1 s)
            self.gpib.write(":FREQ:ARM:STAR:SOUR IMM")
            self.gpib.write(":FREQ:ARM:STOP:SOUR TIM")
            self.gpib.write(":FREQ:ARM:STOP:TIM 1")
            # configura para utilizar oscilador interno
            self.gpib.write(":ROSC:SOUR INT")
            # desativa interpolador automatico
            self.gpib.write(":DIAG:CAL:INT:AUTO OFF")
            # desativa todo o pós-processamento
            self.gpib.write(":CALC:MATH:STATE OFF")
            self.gpib.write(":CALC2:LIM:STATE OFF")
            self.gpib.write(":CALC3:AVER:STATE OFF")
            self.gpib.write(":HCOPY:CONT OFF")
            self.gpib.write("*DDT #15FETC?")
            self.gpib.write(":INIT:CONT ON")

        elif self.modelo == '2182A':
            self.gpib.write("SENS:CHAN 2")
            self.gpib.write(":SENS:VOLT:CHAN2:RANG:AUTO ON")
            self.gpib.write(":SENS:VOLT:NPLC 18")
            self.gpib.write(":SENS:VOLT:DIG 8")
            self.idn = self.gpib.query("*IDN?");
            
        else:
            self.idn = self.gpib.query("*IDN?");
        
    def print_idn(self):
        if self.tipo == 'STD':
            identificacao = 'do padrão'
        elif self.tipo == 'DUT':
            identificacao = 'do objeto'
            
        print("Comunicando com o medidor do "+identificacao+" no endereço "+self.endereco+".")
        print("String de identificação: ")
        print(self.idn)
        print("\n\n")
        return

    def ler_dados(self):
        if self.modelo == '182A':
            x = self.gpib.query("X")
        elif self.modelo == '2182A':
            x = self.gpib.query(":FETCH?")
        elif self.modelo == '53132A':
            x = self.gpib.query(":FETCH:FREQ?")
        elif self.modelo == '3458A':
            x = self.gpib.query("OHM 100E3")
        return x

    def imprimir_dados(self, readings):
        if self.modelo == '182A':
            print(self.tipo+" [mV] {:5.6f}".format(float(readings[-1].replace('NDCV','').strip())*1000))
        elif self.modelo == '2182A':
            print(self.tipo+" [mV] {:5.6f}".format(float(readings[-1].strip())*1000))
        elif self.modelo == '53132A':
            print(self.tipo+" [Hz] {:5.8f}".format(float(readings[-1].strip())))
        elif self.modelo == '3458A':
            print(self.tipo+" [ohms] {:5.8f}".format(float(readings[-1].strip())))
        return

class Configuracoes(QWidget):
    def __init__(self):
        super(Configuracoes, self).__init__()

        self.createParametrosGroupBox()
        self.createPontosGroupBox()
        self.createInterfaceGPIBGroupBox()
        self.createInstrumentosGroupBox()
        self.createButtonsLayout()
        
        mainLayout = QVBoxLayout()
        topLayout = QHBoxLayout()
        top2Layout = QVBoxLayout()
        
        top2Layout.addWidget(self.pontosGroupBox)
        top2Layout.addWidget(self.interfaceGPIBGroupBox)
        
        topLayout.addWidget(self.parametrosGroupBox)
        topLayout.addLayout(top2Layout)
        
        
        mainLayout.addLayout(topLayout)
        mainLayout.addWidget(self.instrumentosGroupBox)
        mainLayout.addLayout(self.buttonsLayout)
        self.setLayout(mainLayout)

        # valores default

        self.voltage.setText("1")
        self.frequency.setText("0.01,0.02,0.03,0.04,0.055,0.06,0.065,0.12,0.3,0.4,0.5,1,10,20,30,50,70,100,200,300,500,700,800,1000")

        self.wait_time.setValue(60)
        self.repeticoes.setValue(12)
        self.repeticoes_aquecimento.setValue(8)

        self.gpib_fonte_ac.setValue(5)
        self.gpib_fonte_dc.setValue(13)
        self.gpib_medidor_std.setValue(20)
        self.gpib_medidor_dut.setValue(21)
        self.gpib_chave.setValue(10)

        self.setWindowTitle("Configurações")
        self.resize(500, 300)

    def createPontosGroupBox(self):
        self.pontosGroupBox = QGroupBox("Pontos de Medição")

        self.voltage_label = QLabel(self)
        self.voltage_label.setText("Tensão [V]")
        self.voltage = QLineEdit(self)

        self.frequency_label = QLabel(self)
        self.frequency_label.setText("Frequências [kHz]")
        self.frequency = QLineEdit(self)

        # layout
        pontosGroupBoxLayout = QGridLayout()

        # Primeira coluna: labels
        pontosGroupBoxLayout.addWidget(self.voltage_label, 0, 0)
        pontosGroupBoxLayout.addWidget(self.frequency_label, 1, 0)

        # Segunda coluna: lineEdit
        pontosGroupBoxLayout.addWidget(self.voltage, 0, 1)
        pontosGroupBoxLayout.addWidget(self.frequency, 1, 1)
        
        self.pontosGroupBox.setLayout(pontosGroupBoxLayout)

    def createInterfaceGPIBGroupBox(self):
        self.interfaceGPIBGroupBox = QGroupBox("Interface GPIB")

        self.gpib_interface_label = QLabel(self)
        self.gpib_interface_label.setText("Número da Interface GPIB")
        self.gpib_interface = QSpinBox()
        self.gpib_interface.setMaximum(1)

        # layout
        interfaceGPIBGroupBoxLayout = QGridLayout()

        # Primeira coluna: labels
        interfaceGPIBGroupBoxLayout.addWidget(self.gpib_interface_label, 0, 0)

        # Segunda coluna: spinbox
        interfaceGPIBGroupBoxLayout.addWidget(self.gpib_interface, 0, 1)
        
        self.interfaceGPIBGroupBox.setLayout(interfaceGPIBGroupBoxLayout)

    def createParametrosGroupBox(self):
        self.parametrosGroupBox = QGroupBox("Parâmetros")

        # tempo de espera
        self.wait_time_label = QLabel(self)
        self.wait_time_label.setText("Tempo de espera [s]")
        self.wait_time = QSpinBox()

        # repeticoes
        self.repeticoes_label = QLabel(self)
        self.repeticoes_label.setText("Repetições")
        self.repeticoes = QSpinBox()

        self.repeticoes_aquecimento_label = QLabel(self)
        self.repeticoes_aquecimento_label.setText("Aquecimento")
        self.repeticoes_aquecimento = QSpinBox()

        # layout
        parametrosGroupBoxLayout = QGridLayout()

        # Primeira coluna: labels
        parametrosGroupBoxLayout.addWidget(self.wait_time_label, 0, 0)
        parametrosGroupBoxLayout.addWidget(self.repeticoes_label, 1, 0)
        parametrosGroupBoxLayout.addWidget(self.repeticoes_aquecimento_label, 2, 0)

        # Segunda coluna: spinbox
        parametrosGroupBoxLayout.addWidget(self.wait_time, 0, 1)
        parametrosGroupBoxLayout.addWidget(self.repeticoes, 1, 1)
        parametrosGroupBoxLayout.addWidget(self.repeticoes_aquecimento, 2, 1)

        self.parametrosGroupBox.setLayout(parametrosGroupBoxLayout)

    def createInstrumentosGroupBox(self):
        self.instrumentosGroupBox = QGroupBox("Instrumentos")

        # definicoes dos campos
        # labels (cabeçalho)
        self.modelo = QLabel(self)
        self.modelo.setText("Modelo")

        self.endereco = QLabel(self)
        self.endereco.setText("Endereço GPIB")
        
        self.remoto = QLabel(self)
        self.remoto.setText("REM?")
        
        self.idn = QLabel(self)
        self.idn.setText("Identificação")

        # fonte ac
        self.gpib_fonte_ac_modelo = QComboBox()
        self.gpib_fonte_ac_modelo.addItem("5700A")
        self.gpib_fonte_ac_modelo.addItem("5720A")
        self.gpib_fonte_ac_modelo.addItem("5730A")        
        self.gpib_fonte_ac = QSpinBox()
        self.gpib_fonte_ac.setMaximum(30)
        self.gpib_fonte_ac_remoto = QCheckBox()
        self.gpib_fonte_ac_remoto.stateChanged.connect(self.gpib_fonte_ac_remoto_changed)
        self.gpib_fonte_ac_idn = QLineEdit(self)
        self.gpib_fonte_ac_idn.setReadOnly(True)
        
        # fonte dc
        self.gpib_fonte_dc_modelo = QComboBox()
        self.gpib_fonte_dc_modelo.addItem("5700A")
        self.gpib_fonte_dc_modelo.addItem("5720A")
        self.gpib_fonte_dc_modelo.addItem("5730A")
        self.gpib_fonte_dc = QSpinBox()
        self.gpib_fonte_dc.setMaximum(30)
        self.gpib_fonte_dc_remoto = QCheckBox()
        self.gpib_fonte_dc_idn = QLineEdit(self)
        self.gpib_fonte_dc_idn.setReadOnly(True)

        # medidor std
        self.gpib_medidor_std_modelo = QComboBox()
        self.gpib_medidor_std_modelo.addItem("182A")
        self.gpib_medidor_std_modelo.addItem("2182A")
        self.gpib_medidor_std_modelo.addItem("3548A")
        self.gpib_medidor_std_modelo.addItem("53131A")
        self.gpib_medidor_std = QSpinBox()
        self.gpib_medidor_std.setMaximum(30)
        self.gpib_medidor_std_remoto = QCheckBox()
        self.gpib_medidor_std_idn = QLineEdit(self)
        self.gpib_medidor_std_idn.setReadOnly(True)
        

        # medidor dut
        self.gpib_medidor_dut_modelo = QComboBox()
        self.gpib_medidor_dut_modelo.addItem("182A")
        self.gpib_medidor_dut_modelo.addItem("2182A")
        self.gpib_medidor_dut_modelo.addItem("3548A")
        self.gpib_medidor_dut_modelo.addItem("53131A")
        self.gpib_medidor_dut = QSpinBox()
        self.gpib_medidor_dut.setMaximum(30)
        self.gpib_medidor_dut_remoto = QCheckBox()
        self.gpib_medidor_dut_idn = QLineEdit(self)
        self.gpib_medidor_dut_idn.setReadOnly(True)

        # chave 
        self.gpib_chave_modelo = QComboBox()
        self.gpib_chave_modelo.addItem("METAS")
        self.gpib_chave = QSpinBox()
        self.gpib_chave.setMaximum(30)
        self.gpib_chave_remoto = QCheckBox()
        self.gpib_chave_idn = QLineEdit(self)
        self.gpib_chave_idn.setReadOnly(True)

        #self.delaySpinBox.valueChanged.connect(self.updateCheckBox)

        # Layout
        instrumentosGroupBoxLayout = QGridLayout()

        # Primeira coluna: selecionar modelo
        instrumentosGroupBoxLayout.addWidget(self.modelo, 0, 0)
        instrumentosGroupBoxLayout.addWidget(self.gpib_fonte_ac_modelo, 1, 0)
        instrumentosGroupBoxLayout.addWidget(self.gpib_fonte_dc_modelo, 2, 0)
        instrumentosGroupBoxLayout.addWidget(self.gpib_medidor_std_modelo, 3, 0)
        instrumentosGroupBoxLayout.addWidget(self.gpib_medidor_dut_modelo, 4, 0)
        instrumentosGroupBoxLayout.addWidget(self.gpib_chave_modelo, 5, 0)

        # Segunda coluna: selecionar endereço GPIB
        instrumentosGroupBoxLayout.addWidget(self.endereco, 0, 1)
        instrumentosGroupBoxLayout.addWidget(self.gpib_fonte_ac, 1, 1)
        instrumentosGroupBoxLayout.addWidget(self.gpib_fonte_dc, 2, 1)
        instrumentosGroupBoxLayout.addWidget(self.gpib_medidor_std, 3, 1)
        instrumentosGroupBoxLayout.addWidget(self.gpib_medidor_dut, 4, 1)
        instrumentosGroupBoxLayout.addWidget(self.gpib_chave, 5, 1)

        # Terceira coluna: checkbox para colocar em remoto
        instrumentosGroupBoxLayout.addWidget(self.remoto, 0, 2)
        instrumentosGroupBoxLayout.addWidget(self.gpib_fonte_ac_remoto, 1, 2)
        instrumentosGroupBoxLayout.addWidget(self.gpib_fonte_dc_remoto, 2, 2)
        instrumentosGroupBoxLayout.addWidget(self.gpib_medidor_std_remoto, 3, 2)
        instrumentosGroupBoxLayout.addWidget(self.gpib_medidor_dut_remoto, 4, 2)
        instrumentosGroupBoxLayout.addWidget(self.gpib_chave_remoto, 5, 2)

        # Quarta coluna: exibir string de identificacao quando em remoto
        instrumentosGroupBoxLayout.addWidget(self.idn, 0, 3)
        instrumentosGroupBoxLayout.addWidget(self.gpib_fonte_ac_idn, 1 ,3)
        instrumentosGroupBoxLayout.addWidget(self.gpib_fonte_dc_idn, 2 ,3)
        instrumentosGroupBoxLayout.addWidget(self.gpib_medidor_std_idn, 3 ,3)
        instrumentosGroupBoxLayout.addWidget(self.gpib_medidor_dut_idn, 4 ,3)
        instrumentosGroupBoxLayout.addWidget(self.gpib_chave_idn, 5 ,3)
        
        self.instrumentosGroupBox.setLayout(instrumentosGroupBoxLayout)

    def gpib_fonte_ac_remoto_changed(self, int):
        if self.gpib_fonte_ac_remoto.isChecked():
            AC = Fonte(str(self.gpib_interface.value()),str(self.gpib_fonte_ac.value()),self.gpib_fonte_ac_modelo.currentText(),'AC')
            self.gpib_fonte_ac_idn.setText(AC.idn)
            #self.gpib_fonte_ac_idn.setText(str(self.gpib_interface.value())+","+str(self.gpib_fonte_ac.value())+","+self.gpib_fonte_ac_modelo.currentText()+","+"AC")
        else:
            AC.gpib.close()
            self.gpib_fonte_ac_idn.setText("")
            

    def createButtonsLayout(self):
##        self.newScreenshotButton = self.createButton("New Screenshot",
##                self.newScreenshot)
##
##        self.saveScreenshotButton = self.createButton("Save Screenshot",
##                self.saveScreenshot)

        self.quitConfig = self.createButton("Sair", self.close)

        self.buttonsLayout = QHBoxLayout()
        self.buttonsLayout.addStretch()
##        self.buttonsLayout.addWidget(self.newScreenshotButton)
##        self.buttonsLayout.addWidget(self.saveScreenshotButton)
        self.buttonsLayout.addWidget(self.quitConfig)

    def createButton(self, text, member):
        button = QPushButton(text)
        button.clicked.connect(member)
        return button


if __name__ == '__main__':

    import sys

    app = QApplication(sys.argv)
    configuracoes = Configuracoes()
    configuracoes.show()
    sys.exit(app.exec_())
