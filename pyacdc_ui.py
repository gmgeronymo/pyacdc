#!/usr/bin/env python

import visa
import datetime
from PyQt5.QtCore import QDir, Qt
from PyQt5.QtWidgets import (QApplication, QCheckBox, QFileDialog, QGridLayout,
        QGroupBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSpinBox,
        QVBoxLayout, QWidget, QComboBox, QLineEdit, QMessageBox, QSpacerItem)
from abc import ABCMeta, abstractmethod
from functools import partial

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
    modelo: modelo do instrumento ('Keithley 182A', 'Keithley 2182A', 'Agilent 53132A', 'Agilent 3458A', etc.)
    tipo: string, assume os valores 'STD' ou 'DUT'
    """
    def __init__(self, bus, endereco, modelo, tipo):
        Instrumento.__init__(self, bus, endereco, modelo)
        if (tipo != 'DUT') & (tipo != 'STD'):
            raise NameError('tipo deve ser STD ou DUT')

        self.tipo = tipo

        if self.modelo == 'Agilent 3458A':
            self.gpib.write("OFORMAT ASCII")
            self.gpib.write("END ALWAYS")
            self.gpib.write("NPLC 8")
            self.idn = self.gpib.query("ID?");
            
        elif self.modelo == 'Keithley 182A':
            self.gpib.write("R0I0B1X")
            self.gpib.write("S2N1X")
            self.gpib.write("O1P2X")
            self.idn = "Keithley 182A"

        elif self.modelo == 'Agilent 53132A':
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

        elif self.modelo == 'Keithley 2182A':
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
        if self.modelo == 'Keithley 182A':
            x = self.gpib.query("X")
        elif self.modelo == 'Keithley 2182A':
            x = self.gpib.query(":FETCH?")
        elif self.modelo == 'Agilent 53132A':
            x = self.gpib.query(":FETCH:FREQ?")
        elif self.modelo == 'Agilent 3458A':
            x = self.gpib.query("OHM 100E3")
        return x

    def imprimir_dados(self, readings):
        if self.modelo == 'Keithley 182A':
            print(self.tipo+" [mV] {:5.6f}".format(float(readings[-1].replace('NDCV','').strip())*1000))
        elif self.modelo == 'Keithley 2182A':
            print(self.tipo+" [mV] {:5.6f}".format(float(readings[-1].strip())*1000))
        elif self.modelo == 'Agilent 53132A':
            print(self.tipo+" [Hz] {:5.8f}".format(float(readings[-1].strip())))
        elif self.modelo == 'Agilent 3458A':
            print(self.tipo+" [ohms] {:5.8f}".format(float(readings[-1].strip())))
        return

class Configuracoes(QWidget):
    def __init__(self):
        super(Configuracoes, self).__init__()

        self.createParametrosGroupBox()
        self.createPontosGroupBox()
        self.createLeiturasGroupBox()
        self.createInstrumentosGroupBox()
        self.createButtonsLayout()
        
        topLayout = QHBoxLayout()
        main2Layout = QHBoxLayout()
        leftLayout = QVBoxLayout()
        mainLayout = QVBoxLayout()
        
        topLayout.addWidget(self.parametrosGroupBox)
        topLayout.addWidget(self.pontosGroupBox)
        
        
        leftLayout.addLayout(topLayout)
        leftLayout.addWidget(self.instrumentosGroupBox)

        main2Layout.addLayout(leftLayout)
        main2Layout.addWidget(self.leiturasGroupBox)

        mainLayout.addLayout(main2Layout) 
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
        self.resize(800, 400)

    def createLeiturasGroupBox(self):

        self.leiturasGroupBox = QGroupBox("Leituras")

        # labels
        self.leiturasAc1Label = QLabel(self)
        self.leiturasAc1Label.setText(" AC")
        self.leiturasDcpLabel = QLabel(self)
        self.leiturasDcpLabel.setText("+DC")
        self.leiturasAc2Label = QLabel(self)
        self.leiturasAc2Label.setText(" AC")
        self.leiturasDcmLabel = QLabel(self)
        self.leiturasDcmLabel.setText("-DC")
        self.leiturasAc3Label = QLabel(self)
        self.leiturasAc3Label.setText(" AC")

        # padrao
        self.leiturasPadraoLabel = QLabel(self)
        self.leiturasPadraoLabel.setText("Padrão [mV]")
        self.leiturasPadraoAc1 = QLineEdit(self)
        self.leiturasPadraoAc1.setReadOnly(True)
        self.leiturasPadraoAc2 = QLineEdit(self)
        self.leiturasPadraoAc2.setReadOnly(True)
        self.leiturasPadraoAc3 = QLineEdit(self)
        self.leiturasPadraoAc3.setReadOnly(True)
        self.leiturasPadraoDcp = QLineEdit(self)
        self.leiturasPadraoDcp.setReadOnly(True)
        self.leiturasPadraoDcm = QLineEdit(self)
        self.leiturasPadraoDcm.setReadOnly(True)

        # objeto
        self.leiturasObjetoLabel = QLabel(self)
        self.leiturasObjetoLabel.setText("Objeto [mV]")
        self.leiturasObjetoAc1 = QLineEdit(self)
        self.leiturasObjetoAc1.setReadOnly(True)
        self.leiturasObjetoAc2 = QLineEdit(self)
        self.leiturasObjetoAc2.setReadOnly(True)
        self.leiturasObjetoAc3 = QLineEdit(self)
        self.leiturasObjetoAc3.setReadOnly(True)
        self.leiturasObjetoDcp = QLineEdit(self)
        self.leiturasObjetoDcp.setReadOnly(True)
        self.leiturasObjetoDcm = QLineEdit(self)
        self.leiturasObjetoDcm.setReadOnly(True)

        # tempo de espera
        self.esperaCounterLabel = QLabel(self)
        self.esperaCounterLabel.setText("Espera")
        self.esperaCounter = QLineEdit(self)
        self.esperaCounter.setReadOnly(True)
        self.esperaTotal = QLineEdit(self)
        self.esperaTotal.setReadOnly(True)

        # repeticoes
        self.repeticoesCounterLabel = QLabel(self)
        self.repeticoesCounterLabel.setText("Repetições")
        self.repeticoesCounter = QLineEdit(self)
        self.repeticoesCounter.setReadOnly(True)
        self.repeticoesTotal = QLineEdit(self)
        self.repeticoesTotal.setReadOnly(True)

        # coeficiente n
        self.coeficienteNLabel = QLabel(self)
        self.coeficienteNLabel.setText("Coeficiente n")
        self.nPadraoLabel = QLabel(self)
        self.nPadraoLabel.setText("Padrão")
        self.nObjetoLabel = QLabel(self)
        self.nObjetoLabel.setText("Objeto")
        self.nPadrao = QLineEdit(self)
        self.nPadrao.setReadOnly(True)
        self.nObjeto = QLineEdit(self)
        self.nObjeto.setReadOnly(True)

        verticalSpacer = QSpacerItem(20, 40)

        # layout

        leiturasGroupBoxLayout = QGridLayout()

        leiturasGroupBoxLayout.addWidget(self.leiturasPadraoLabel, 0, 1)
        leiturasGroupBoxLayout.addWidget(self.leiturasObjetoLabel, 0, 2)
        
        leiturasGroupBoxLayout.addWidget(self.leiturasAc1Label, 1, 0)
        leiturasGroupBoxLayout.addWidget(self.leiturasPadraoAc1, 1, 1)
        leiturasGroupBoxLayout.addWidget(self.leiturasObjetoAc1, 1, 2)
        
        leiturasGroupBoxLayout.addWidget(self.leiturasDcpLabel, 2, 0)
        leiturasGroupBoxLayout.addWidget(self.leiturasPadraoDcp, 2, 1)
        leiturasGroupBoxLayout.addWidget(self.leiturasObjetoDcp, 2, 2)

        leiturasGroupBoxLayout.addWidget(self.leiturasAc2Label, 3, 0)
        leiturasGroupBoxLayout.addWidget(self.leiturasPadraoAc2, 3, 1)
        leiturasGroupBoxLayout.addWidget(self.leiturasObjetoAc2, 3, 2)

        leiturasGroupBoxLayout.addWidget(self.leiturasDcmLabel, 4, 0)
        leiturasGroupBoxLayout.addWidget(self.leiturasPadraoDcm, 4, 1)
        leiturasGroupBoxLayout.addWidget(self.leiturasObjetoDcm, 4, 2)

        leiturasGroupBoxLayout.addWidget(self.leiturasAc3Label, 5, 0)
        leiturasGroupBoxLayout.addWidget(self.leiturasPadraoAc3, 5, 1)
        leiturasGroupBoxLayout.addWidget(self.leiturasObjetoAc3, 5, 2)

        leiturasGroupBoxLayout.addItem(verticalSpacer)

        leiturasGroupBoxLayout.addWidget(self.esperaCounterLabel, 7, 0)
        leiturasGroupBoxLayout.addWidget(self.esperaCounter, 7, 1)
        leiturasGroupBoxLayout.addWidget(self.esperaTotal, 7, 2)

        leiturasGroupBoxLayout.addWidget(self.repeticoesCounterLabel, 8, 0)
        leiturasGroupBoxLayout.addWidget(self.repeticoesCounter, 8, 1)
        leiturasGroupBoxLayout.addWidget(self.repeticoesTotal, 8, 2)

        leiturasGroupBoxLayout.addItem(verticalSpacer)

        leiturasGroupBoxLayout.addWidget(self.nPadraoLabel, 10, 1)
        leiturasGroupBoxLayout.addWidget(self.nObjetoLabel, 10, 2)

        leiturasGroupBoxLayout.addWidget(self.coeficienteNLabel, 11, 0)
        leiturasGroupBoxLayout.addWidget(self.nPadrao, 11, 1)
        leiturasGroupBoxLayout.addWidget(self.nObjeto, 11, 2)        

        self.leiturasGroupBox.setLayout(leiturasGroupBoxLayout)

    def createPontosGroupBox(self):
        self.pontosGroupBox = QGroupBox("Pontos de Medição")

        self.padraoLabel = QLabel(self)
        self.padraoLabel.setText("Identificação do Padrão")
        self.padrao = QLineEdit(self)

        self.objetoLabel = QLabel(self)
        self.objetoLabel.setText("Identificação do Objeto")
        self.objeto = QLineEdit(self)

        self.voltageLabel = QLabel(self)
        self.voltageLabel.setText("Tensão [V]")
        self.voltage = QLineEdit(self)

        self.frequencyLabel = QLabel(self)
        self.frequencyLabel.setText("Frequências [kHz]")
        self.frequency = QLineEdit(self)

        self.observacoesLabel = QLabel(self)
        self.observacoesLabel.setText("Observações")
        self.observacoes = QLineEdit(self)

        # layout
        pontosGroupBoxLayout = QGridLayout()

        pontosGroupBoxLayout.addWidget(self.padraoLabel, 0, 0)
        pontosGroupBoxLayout.addWidget(self.padrao, 0, 1)
        
        pontosGroupBoxLayout.addWidget(self.objetoLabel, 1, 0)
        pontosGroupBoxLayout.addWidget(self.objeto, 1, 1)
        
        pontosGroupBoxLayout.addWidget(self.voltageLabel, 2, 0)
        pontosGroupBoxLayout.addWidget(self.voltage, 2, 1)

        pontosGroupBoxLayout.addWidget(self.frequencyLabel, 3, 0)
        pontosGroupBoxLayout.addWidget(self.frequency, 3, 1)

        pontosGroupBoxLayout.addWidget(self.observacoesLabel, 4, 0)
        pontosGroupBoxLayout.addWidget(self.observacoes, 4, 1)
        
        self.pontosGroupBox.setLayout(pontosGroupBoxLayout)

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

        # aquecimento

        self.repeticoesAquecimentoLabel = QLabel(self)
        self.repeticoesAquecimentoLabel.setText("Aquecimento")
        self.repeticoesAquecimento = QSpinBox()

        # gpib bus
        
        self.gpibBusLabel = QLabel(self)
        self.gpibBusLabel.setText("GPIB Bus")
        self.gpibBus = QSpinBox()
        self.gpibBus.setMaximum(1)

        # layout
        parametrosGroupBoxLayout = QGridLayout()

        # Primeira coluna: labels
        parametrosGroupBoxLayout.addWidget(self.waitTimeLabel, 0, 0)
        parametrosGroupBoxLayout.addWidget(self.repeticoesLabel, 1, 0)
        parametrosGroupBoxLayout.addWidget(self.repeticoesAquecimentoLabel, 2, 0)
        parametrosGroupBoxLayout.addWidget(self.gpibBusLabel, 3, 0)

        # Segunda coluna: spinbox
        parametrosGroupBoxLayout.addWidget(self.waitTime, 0, 1)
        parametrosGroupBoxLayout.addWidget(self.repeticoes, 1, 1)
        parametrosGroupBoxLayout.addWidget(self.repeticoesAquecimento, 2, 1)
        parametrosGroupBoxLayout.addWidget(self.gpibBus, 3, 1)

        self.parametrosGroupBox.setLayout(parametrosGroupBoxLayout)

    def createInstrumentosGroupBox(self):
        self.instrumentosGroupBox = QGroupBox("Instrumentos")

        # definicoes dos campos
        # labels (cabeçalho)
        #self.id = QLabel(self)
        #self.id.setText("Instrumento")

        self.remoto = QLabel(self)
        self.remoto.setText("Remoto?")
        
        self.modelo = QLabel(self)
        self.modelo.setText("Modelo")

        self.endereco = QLabel(self)
        self.endereco.setText("Endereço GPIB")
        
        self.idn = QLabel(self)
        self.idn.setText("Identificação")

        # fonte ac
        self.fonteAcRemoto = QCheckBox("Fonte AC")
        slotFonteAc = partial(self.controleRemoto, self.fonteAcRemoto)
        self.fonteAcRemoto.stateChanged.connect(lambda x: slotFonteAc())
        self.fonteAcModelo = QComboBox()
        self.fonteAcModelo.addItem("Fluke 5700A")
        self.fonteAcModelo.addItem("Fluke 5720A")
        self.fonteAcModelo.addItem("Fluke 5730A")        
        self.fonteAcEndereco = QSpinBox()
        self.fonteAcEndereco.setMaximum(30)       
        self.fonteAcIdn = QLineEdit(self)
        self.fonteAcIdn.setReadOnly(True)
        
        # fonte dc
        self.fonteDcRemoto = QCheckBox("Fonte DC")
        slotFonteDc = partial(self.controleRemoto, self.fonteDcRemoto)
        self.fonteDcRemoto.stateChanged.connect(lambda x: slotFonteDc())
        self.fonteDcModelo = QComboBox()
        self.fonteDcModelo.addItem("Fluke 5700A")
        self.fonteDcModelo.addItem("Fluke 5720A")
        self.fonteDcModelo.addItem("Fluke 5730A")        
        self.fonteDcEndereco = QSpinBox()
        self.fonteDcEndereco.setMaximum(30)
        self.fonteDcIdn = QLineEdit(self)
        self.fonteDcIdn.setReadOnly(True)

        # medidor std
        self.medidorStdRemoto = QCheckBox("Medidor do Padrão")
        slotMedidorStd = partial(self.controleRemoto, self.medidorStdRemoto)
        self.medidorStdRemoto.stateChanged.connect(lambda x: slotMedidorStd())
        self.medidorStdModelo = QComboBox()
        self.medidorStdModelo.addItem("Keithley 182A")
        self.medidorStdModelo.addItem("Keithley 2182A")
        self.medidorStdModelo.addItem("Agilent 3548A")
        self.medidorStdModelo.addItem("Agilent 53132A")
        self.medidorStdEndereco = QSpinBox()
        self.medidorStdEndereco.setMaximum(30)
        self.medidorStdIdn = QLineEdit(self)
        self.medidorStdIdn.setReadOnly(True)
        

        # medidor dut
        self.medidorDutRemoto = QCheckBox("Medidor do Objeto")
        slotMedidorDut = partial(self.controleRemoto, self.medidorDutRemoto)
        self.medidorDutRemoto.stateChanged.connect(lambda x: slotMedidorDut())
        self.medidorDutModelo = QComboBox()
        self.medidorDutModelo.addItem("Keithley 182A")
        self.medidorDutModelo.addItem("Keithley 2182A")
        self.medidorDutModelo.addItem("Agilent 3548A")
        self.medidorDutModelo.addItem("Agilent 53132A")
        self.medidorDutEndereco = QSpinBox()
        self.medidorDutEndereco.setMaximum(30)
        self.medidorDutIdn = QLineEdit(self)
        self.medidorDutIdn.setReadOnly(True)

        # chave
        self.chaveRemoto = QCheckBox("Chave AC/DC")
        slotChave = partial(self.controleRemoto, self.chaveRemoto)
        self.chaveRemoto.stateChanged.connect(lambda x: slotChave())
        self.chaveModelo = QComboBox()
        self.chaveModelo.addItem("METAS")
        self.chaveEndereco = QSpinBox()
        self.chaveEndereco.setMaximum(30)      
        self.chaveIdn = QLineEdit(self)
        self.chaveIdn.setReadOnly(True)

        # Layout
        instrumentosGroupBoxLayout = QGridLayout()

        # Coluna zero: checkbox para colocar em remoto
        instrumentosGroupBoxLayout.addWidget(self.remoto, 0, 0)
        instrumentosGroupBoxLayout.addWidget(self.fonteAcRemoto, 1, 0)
        instrumentosGroupBoxLayout.addWidget(self.fonteDcRemoto, 2, 0)
        instrumentosGroupBoxLayout.addWidget(self.medidorStdRemoto, 3, 0)
        instrumentosGroupBoxLayout.addWidget(self.medidorDutRemoto, 4, 0)
        instrumentosGroupBoxLayout.addWidget(self.chaveRemoto, 5, 0)

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

        
        # Coluna três: exibir string de identificacao quando em remoto
        instrumentosGroupBoxLayout.addWidget(self.idn, 0, 3)
        instrumentosGroupBoxLayout.addWidget(self.fonteAcIdn, 1, 3)
        instrumentosGroupBoxLayout.addWidget(self.fonteDcIdn, 2, 3)
        instrumentosGroupBoxLayout.addWidget(self.medidorStdIdn, 3, 3)
        instrumentosGroupBoxLayout.addWidget(self.medidorDutIdn, 4, 3)
        instrumentosGroupBoxLayout.addWidget(self.chaveIdn, 5, 3)
        
        self.instrumentosGroupBox.setLayout(instrumentosGroupBoxLayout)

    def controleRemoto(self, checkbox):
        if checkbox.isChecked():
            try:
                if checkbox.text() == "Fonte AC":
                    self.AC = Fonte(str(self.gpibBus.value()),str(self.fonteAcEndereco.value()),self.fonteAcModelo.currentText(),'AC')
                    self.fonteAcIdn.setText(self.AC.idn)
                elif checkbox.text() == "Fonte DC":
                    self.DC = Fonte(str(self.gpibBus.value()),str(self.fonteDcEndereco.value()),self.fonteDcModelo.currentText(),'DC')
                    self.fonteDcIdn.setText(self.DC.idn)
                elif checkbox.text() == "Medidor do Padrão":
                    self.STD = Medidor(str(self.gpibBus.value()),str(self.medidorStdEndereco.value()),self.medidorStdModelo.currentText(),'STD')
                    self.medidorStdIdn.setText(self.STD.idn)
                elif checkbox.text() == "Medidor do Objeto":
                    self.DUT = Medidor(str(self.gpibBus.value()),str(self.medidorDutEndereco.value()),self.medidorDutModelo.currentText(),'DUT')
                    self.medidorDutIdn.setText(self.DUT.idn)
                elif checkbox.text() == "Chave AC/DC":
                    self.SW = Chave(str(self.gpibBus.value()),str(self.chaveEndereco.value()),self.chaveModelo.currentText())
                    self.chaveIdn.setText(self.SW.idn)
                    
            except:
                QMessageBox.critical(self, "Erro",
                "Erro ao conectar com o instrumento!",
                QMessageBox.Abort)
                
        else:
            try:
                if checkbox.text() == "Fonte AC":
                    self.AC.gpib.control_ren(0)
                    self.fonteAcIdn.setText("")
                elif checkbox.text() == "Fonte DC":
                    self.DC.gpib.control_ren(0)
                    self.fonteDcIdn.setText("")
                elif checkbox.text() == "Medidor do Padrão":
                    self.STD.gpib.control_ren(0)
                    self.medidorStdIdn.setText.setText("")
                elif checkbox.text() == "Medidor do Objeto":
                    self.DUT.gpib.control_ren(0)
                    self.medidorDutIdn.setText("")
                elif checkbox.text() == "Chave AC/DC":
                    self.SW.gpib.control_ren(0)
                    self.chaveIdn.setText("")
            except:
                #QMessageBox.critical(self, "Erro",
                #"Erro ao conectar com o instrumento!",
                #QMessageBox.Abort)
                self.chaveIdn.setText("")
            

    def createButtonsLayout(self):
##        self.newScreenshotButton = self.createButton("New Screenshot",
##                self.newScreenshot)
##
##        self.saveScreenshotButton = self.createButton("Save Screenshot",
##                self.saveScreenshot)

        self.quitConfig = self.createButton("Sair", self.close)
        self.medir = self.createButton("Medir", self.close)
        self.parar = self.createButton("Parar", self.close)

        self.buttonsLayout = QHBoxLayout()
        self.buttonsLayout.addStretch()
        self.buttonsLayout.addWidget(self.medir)
        self.buttonsLayout.addWidget(self.parar)
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
