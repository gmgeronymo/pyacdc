#!/usr/bin/env python

import visa
import datetime
from PyQt5.QtCore import QDir, Qt
from PyQt5.QtWidgets import (QApplication, QCheckBox, QFileDialog, QGridLayout,
        QGroupBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSpinBox,
        QVBoxLayout, QWidget, QComboBox, QLineEdit)
from abc import ABCMeta, abstractmethod

# Constantes e variáveis globais
# comandos da chave (em ASCII puro)
reset = chr(2)
ac = chr(4)
dc = chr(6)

rm = visa.ResourceManager()

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

#-------------------------------------------------------------------------------
        
class Chave(Instrumento):
    """ Classe para a chave AC-DC
    Atributos:
    endereco: string com o endereço GPIB do instrumento
    modelo: modelo do instrumento ('METAS')
    """

    def __init__(self,bus,endereco,modelo):
        Instrumento.__init__(self, bus, endereco,modelo)
        self.idn = "METAS AC/DC Switch"
    
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
        Instrumento.__init__(self, bus, endereco, modelo)
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

        self.waitTime.setValue(60)
        self.repeticoes.setValue(12)
        self.repeticoesAquecimento.setValue(8)

        self.fonteAcEndereco.setValue(5)
        self.fonteDcEndereco.setValue(13)
        self.medidorStdEndereco.setValue(20)
        self.medidorDutEndereco.setValue(21)
        self.chaveEndereco.setValue(10)

        self.setWindowTitle("Configurações")
        self.resize(600, 400)

    def createPontosGroupBox(self):
        self.pontosGroupBox = QGroupBox("Pontos de Medição")

        self.voltageLabel = QLabel(self)
        self.voltageLabel.setText("Tensão [V]")
        self.voltage = QLineEdit(self)

        self.frequencyLabel = QLabel(self)
        self.frequencyLabel.setText("Frequências [kHz]")
        self.frequency = QLineEdit(self)

        # layout
        pontosGroupBoxLayout = QGridLayout()

        # Primeira coluna: labels
        pontosGroupBoxLayout.addWidget(self.voltageLabel, 0, 0)
        pontosGroupBoxLayout.addWidget(self.frequencyLabel, 1, 0)

        # Segunda coluna: lineEdit
        pontosGroupBoxLayout.addWidget(self.voltage, 0, 1)
        pontosGroupBoxLayout.addWidget(self.frequency, 1, 1)
        
        self.pontosGroupBox.setLayout(pontosGroupBoxLayout)

    def createInterfaceGPIBGroupBox(self):
        self.interfaceGPIBGroupBox = QGroupBox("Interface GPIB")

        self.gpibBusLabel = QLabel(self)
        self.gpibBusLabel.setText("Número da Interface GPIB")
        self.gpibBus = QSpinBox()
        self.gpibBus.setMaximum(1)

        # layout
        interfaceGPIBGroupBoxLayout = QGridLayout()

        # Primeira coluna: labels
        interfaceGPIBGroupBoxLayout.addWidget(self.gpibBusLabel, 0, 0)

        # Segunda coluna: spinbox
        interfaceGPIBGroupBoxLayout.addWidget(self.gpibBus, 0, 1)
        
        self.interfaceGPIBGroupBox.setLayout(interfaceGPIBGroupBoxLayout)

    def createParametrosGroupBox(self):
        self.parametrosGroupBox = QGroupBox("Parâmetros")

        # tempo de espera
        self.waitTimeLabel = QLabel(self)
        self.waitTimeLabel.setText("Tempo de espera [s]")
        self.waitTime = QSpinBox()

        # repeticoes
        self.repeticoesLabel = QLabel(self)
        self.repeticoesLabel.setText("Repetições")
        self.repeticoes = QSpinBox()

        self.repeticoesAquecimentoLabel = QLabel(self)
        self.repeticoesAquecimentoLabel.setText("Aquecimento")
        self.repeticoesAquecimento = QSpinBox()

        # layout
        parametrosGroupBoxLayout = QGridLayout()

        # Primeira coluna: labels
        parametrosGroupBoxLayout.addWidget(self.waitTimeLabel, 0, 0)
        parametrosGroupBoxLayout.addWidget(self.repeticoesLabel, 1, 0)
        parametrosGroupBoxLayout.addWidget(self.repeticoesAquecimentoLabel, 2, 0)

        # Segunda coluna: spinbox
        parametrosGroupBoxLayout.addWidget(self.waitTime, 0, 1)
        parametrosGroupBoxLayout.addWidget(self.repeticoes, 1, 1)
        parametrosGroupBoxLayout.addWidget(self.repeticoesAquecimento, 2, 1)

        self.parametrosGroupBox.setLayout(parametrosGroupBoxLayout)

    def createInstrumentosGroupBox(self):
        self.instrumentosGroupBox = QGroupBox("Instrumentos")

        # definicoes dos campos
        # labels (cabeçalho)
        self.id = QLabel(self)
        self.id.setText("Instrumento")
        
        self.modelo = QLabel(self)
        self.modelo.setText("Modelo")

        self.endereco = QLabel(self)
        self.endereco.setText("Endereço GPIB")
        
        self.remoto = QLabel(self)
        self.remoto.setText("REM?")
        
        self.idn = QLabel(self)
        self.idn.setText("Identificação")

        # fonte ac
        self.fonteAcId = QLabel(self)
        self.fonteAcId.setText("Fonte AC")
        self.fonteAcModelo = QComboBox()
        self.fonteAcModelo.addItem("Fluke 5700A")
        self.fonteAcModelo.addItem("Fluke 5720A")
        self.fonteAcModelo.addItem("Fluke 5730A")        
        self.fonteAcEndereco = QSpinBox()
        self.fonteAcEndereco.setMaximum(30)
        self.fonteAcRemoto = QCheckBox()
        self.fonteAcRemoto.stateChanged.connect(self.fonteAcRemotoChanged)
        self.fonteAcIdn = QLineEdit(self)
        self.fonteAcIdn.setReadOnly(True)
        
        # fonte dc
        self.fonteDcId = QLabel(self)
        self.fonteDcId.setText("Fonte DC")
        self.fonteDcModelo = QComboBox()
        self.fonteDcModelo.addItem("Fluke 5700A")
        self.fonteDcModelo.addItem("Fluke 5720A")
        self.fonteDcModelo.addItem("Fluke 5730A")        
        self.fonteDcEndereco = QSpinBox()
        self.fonteDcEndereco.setMaximum(30)
        self.fonteDcRemoto = QCheckBox()
        self.fonteDcRemoto.stateChanged.connect(self.fonteDcRemotoChanged)
        self.fonteDcIdn = QLineEdit(self)
        self.fonteDcIdn.setReadOnly(True)

        # medidor std
        self.medidorStdId = QLabel(self)
        self.medidorStdId.setText("Medidor do Padrão")
        self.medidorStdModelo = QComboBox()
        self.medidorStdModelo.addItem("Keithley 182A")
        self.medidorStdModelo.addItem("Keithley 2182A")
        self.medidorStdModelo.addItem("Agilent 3548A")
        self.medidorStdModelo.addItem("Agilent 53131A")
        self.medidorStdEndereco = QSpinBox()
        self.medidorStdEndereco.setMaximum(30)
        self.medidorStdRemoto = QCheckBox()
        self.medidorStdRemoto.stateChanged.connect(self.medidorStdRemotoChanged)
        self.medidorStdIdn = QLineEdit(self)
        self.medidorStdIdn.setReadOnly(True)
        

        # medidor dut
        self.medidorDutId = QLabel(self)
        self.medidorDutId.setText("Medidor do Objeto")
        self.medidorDutModelo = QComboBox()
        self.medidorDutModelo.addItem("Keithley 182A")
        self.medidorDutModelo.addItem("Keithley 2182A")
        self.medidorDutModelo.addItem("Agilent 3548A")
        self.medidorDutModelo.addItem("Agilent 53131A")
        self.medidorDutEndereco = QSpinBox()
        self.medidorDutEndereco.setMaximum(30)
        self.medidorDutRemoto = QCheckBox()
        self.medidorDutRemoto.stateChanged.connect(self.medidorDutRemotoChanged)
        self.medidorDutIdn = QLineEdit(self)
        self.medidorDutIdn.setReadOnly(True)

        # chave
        self.chaveId = QLabel(self)
        self.chaveId.setText("Chave AC/DC")
        self.chaveModelo = QComboBox()
        self.chaveModelo.addItem("METAS")
        self.chaveEndereco = QSpinBox()
        self.chaveEndereco.setMaximum(30)
        self.chaveRemoto = QCheckBox()
        self.chaveRemoto.stateChanged.connect(self.chaveRemotoChanged)
        self.chaveIdn = QLineEdit(self)
        self.chaveIdn.setReadOnly(True)

        # Layout
        instrumentosGroupBoxLayout = QGridLayout()

        # Coluna zero: identificacao dos instrumentos

        instrumentosGroupBoxLayout.addWidget(self.id, 0, 0)
        instrumentosGroupBoxLayout.addWidget(self.fonteAcId, 1, 0)
        instrumentosGroupBoxLayout.addWidget(self.fonteDcId, 2, 0)
        instrumentosGroupBoxLayout.addWidget(self.medidorStdId, 3, 0)
        instrumentosGroupBoxLayout.addWidget(self.medidorDutId, 4, 0)
        instrumentosGroupBoxLayout.addWidget(self.chaveId, 5, 0)

        # Coluna um: selecionar modelo
        instrumentosGroupBoxLayout.addWidget(self.modelo, 0, 1)
        instrumentosGroupBoxLayout.addWidget(self.fonteAcModelo, 1, 1)
        instrumentosGroupBoxLayout.addWidget(self.fonteDcModelo, 2, 1)
        instrumentosGroupBoxLayout.addWidget(self.medidorStdModelo, 3, 1)
        instrumentosGroupBoxLayout.addWidget(self.medidorDutModelo, 4, 1)
        instrumentosGroupBoxLayout.addWidget(self.chaveModelo, 5, 1)

        # Coluna dois: selecionar endereço GPIB
        instrumentosGroupBoxLayout.addWidget(self.endereco, 0, 2)
        instrumentosGroupBoxLayout.addWidget(self.fonteAcEndereco, 1, 2)
        instrumentosGroupBoxLayout.addWidget(self.fonteDcEndereco, 2, 2)
        instrumentosGroupBoxLayout.addWidget(self.medidorStdEndereco, 3, 2)
        instrumentosGroupBoxLayout.addWidget(self.medidorDutEndereco, 4, 2)
        instrumentosGroupBoxLayout.addWidget(self.chaveEndereco, 5, 2)

        # Coluna três: checkbox para colocar em remoto
        instrumentosGroupBoxLayout.addWidget(self.remoto, 0, 3)
        instrumentosGroupBoxLayout.addWidget(self.fonteAcRemoto, 1, 3)
        instrumentosGroupBoxLayout.addWidget(self.fonteDcRemoto, 2, 3)
        instrumentosGroupBoxLayout.addWidget(self.medidorStdRemoto, 3, 3)
        instrumentosGroupBoxLayout.addWidget(self.medidorDutRemoto, 4, 3)
        instrumentosGroupBoxLayout.addWidget(self.chaveRemoto, 5, 3)

        # Coluna quatro: exibir string de identificacao quando em remoto
        instrumentosGroupBoxLayout.addWidget(self.idn, 0, 4)
        instrumentosGroupBoxLayout.addWidget(self.fonteAcIdn, 1 ,4)
        instrumentosGroupBoxLayout.addWidget(self.fonteDcIdn, 2 ,4)
        instrumentosGroupBoxLayout.addWidget(self.medidorStdIdn, 3 ,4)
        instrumentosGroupBoxLayout.addWidget(self.medidorDutIdn, 4 ,4)
        instrumentosGroupBoxLayout.addWidget(self.chaveIdn, 5 ,4)
        
        self.instrumentosGroupBox.setLayout(instrumentosGroupBoxLayout)

    def fonteAcRemotoChanged(self, int):
        if self.fonteAcRemoto.isChecked():
            self.AC = Fonte(str(self.gpibBus.value()),str(self.fonteAcEndereco.value()),self.fonteAcModelo.currentText(),'AC')
            self.fonteAcIdn.setText(self.AC.idn)    
        else:            
            self.fonteAcIdn.setText("")
            self.AC.gpib.control_ren(0)
        return

    def fonteDcRemotoChanged(self, int):
        if self.fonteDcRemoto.isChecked():
            self.DC = Fonte(str(self.gpibBus.value()),str(self.fonteDcEndereco.value()),self.fonteDcModelo.currentText(),'DC')
            self.fonteDcIdn.setText(self.DC.idn)
        else:            
            self.fonteDcIdn.setText("")
            self.DC.gpib.control_ren(0)
        return

    def medidorStdRemotoChanged(self, int):
        if self.medidorStdRemoto.isChecked():
            self.STD = Medidor(str(self.gpibBus.value()),str(self.medidorStdEndereco.value()),self.medidorStdModelo.currentText(),'STD')
            self.medidorStdIdn.setText(self.STD.idn)
        else:            
            self.medidorStdIdn.setText("")
            self.STD.gpib.control_ren(0)
        return

    def medidorDutRemotoChanged(self, int):
        if self.medidorDutRemoto.isChecked():
            self.DUT = Medidor(str(self.gpibBus.value()),str(self.medidorDutEndereco.value()),self.medidorDutModelo.currentText(),'DUT')
            self.medidorDutIdn.setText(self.DUT.idn)
        else:            
            self.medidorDutIdn.setText("")
            self.DUT.gpib.control_ren(0)
        return

    def chaveRemotoChanged(self, int):
        if self.chaveRemoto.isChecked():
            self.SW = Chave(str(self.gpibBus.value()),str(self.chaveEndereco.value()),self.chaveModelo.currentText())
            self.chaveIdn.setText(self.SW.idn)
        else:            
            self.chaveIdn.setText("")
            self.SW.gpib.control_ren(0)
        return
            

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
