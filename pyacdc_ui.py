#!/usr/bin/env python

import visa
import datetime
import time
import numpy
import csv
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

# inicializacao do módulo VISA
rm = visa.ResourceManager()

# variaveis globais dos instrumentos
AC = None
DC = None
STD = None
DUT = None
SW = None

# variáveis globais dos parâmetros
freq_array = None
freq = None
v_nominal = None
repeticoes = None
wait_time = None
heating_time = None

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
            #self.gpib.write("R0I0B1X")
            #self.gpib.write("S2N1X")
            #self.gpib.write("O1P2X")
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

    def mostrar_leituras(self, readings, ciclo):
        if self.modelo == 'Keithley 182A':
            if self.tipo == 'STD':
                self.leiturasPadrao[ciclo].setText("{:5.6f}".format(float(readings[-1].replace('NDCV','').strip())*1000))
            else:
                self.leiturasObjeto[ciclo].setText("{:5.6f}".format(float(readings[-1].replace('NDCV','').strip())*1000))
        elif self.modelo == 'Keithley 2182A':
            if self.tipo == 'STD':
                self.leiturasPadrao[ciclo].setText("{:5.6f}".format(float(readings[-1].strip())*1000))
            else:
                self.leiturasObjeto[ciclo].setText("{:5.6f}".format(float(readings[-1].strip())*1000))
        elif self.modelo == 'Agilent 53132A':
            if self.tipo == 'STD':
                self.leiturasPadrao[ciclo].setText("{:5.8f}".format(float(readings[-1].strip())))
            else:
                self.leiturasObjeto[ciclo].setText("{:5.8f}".format(float(readings[-1].strip())))
        elif self.modelo == 'Agilent 3458A':
            if self.tipo == 'STD':
                self.leiturasPadrao[ciclo].setText("{:5.8f}".format(float(readings[-1].strip())))
            else:
                self.leiturasObjeto[ciclo].setText("{:5.8f}".format(float(readings[-1].strip())))
        return

class Medicao(object):
    """ Classe do processo de medição
    Atributos:
    fonte_ac: objeto pyVISA da fonte ac
    fonte_dc: objeto pyVISA da fonte dc
    medidor_std: objeto pyVISA do medidor do padrao
    medidor_dut: objeto pyVISA do medidor do objeto
    chave: objeto pyVISA da chave
    """

    def __init__(self, fonte_ac, fonte_dc, medidor_std, medidor_dut, chave):
        self.fonte_ac = fonte_ac
        self.fonte_dc = fonte_dc
        self.medidor_std = medidor_std
        self.medidor_dut = medidor_dut
        self.chave = chave

    def inicializar(self):
        print("OUT +{:.6f} V".format(v_nominal))
        
        # configuração da fonte AC
        self.fonte_ac.gpib.write("OUT +{:.6f} V".format(v_nominal));
        self.fonte_ac.gpib.write("OUT 1000 HZ");
        # configuração da fonte DC
        self.fonte_dc.gpib.write("OUT +{:.6f} V".format(v_nominal));
        self.fonte_dc.gpib.write("OUT 0 HZ");
        # Entrar em OPERATE
        espera(2); # esperar 2 segundos
        self.fonte_ac.gpib.write("*CLS");
        self.fonte_ac.gpib.write("OPER");
        self.fonte_dc.gpib.write("*CLS");
        self.fonte_dc.gpib.write("OPER");
        espera(10);
        self.chave.gpib.write_raw(ac);
        espera(10);
        return

    def aquecimento(self, tempo):
    # executa o aquecimento, mantendo a tensão nominal aplicada pelo tempo
    # (em segundos) definido na variavel "tempo", alternando entre AC e DC
    # a cada 60 segundos
        rep = int(tempo / 120);
        self.fonte_dc.gpib.write("OUT +{:.6f} V".format(v_nominal));
        self.fonte_dc.gpib.write("OUT 0 HZ");
        self.fonte_ac.gpib.write("OUT +{:.6f} V".format(v_nominal));
        self.fonte_ac.gpib.write("OUT 1000 HZ");

        for i in range(0,rep):
            self.chave.gpib.write_raw(dc);
            espera(60);
            self.chave.gpib.write_raw(ac);
            espera(60);
        return

    def medir_n(self, M):
        # testa se M é par, se não for, soma 1 para se tornar par
        if int(M) % 2 != 0:
            M += 1;
        # define as variáveis que armazenam as leituras do padrão e do objeto
        std_readings = []
        dut_readings = []
        # variavel da constante V0 / (Vi-V0)
        self.k = []
        # aplica o valor nominal de tensão
        self.fonte_ac.gpib.write("OUT {:.6f} V".format(v_nominal));
        self.fonte_ac.gpib.write("OUT "+str(freq)+" HZ");
        self.fonte_dc.gpib.write("OUT +{:.6f} V".format(v_nominal));
        espera(2); # espera 2 segundos
        self.chave.gpib.write_raw(dc);
        print("Vdc nominal: +{:.6f} V".format(v_nominal))
        # aguarda pelo tempo de espera configurado
        espera(wait_time);
        # lê as saídas de padrão e objeto, e armazena na variável std_readings e
        # dut_readings
        std_readings.append(self.medidor_std.ler_dados())
        dut_readings.append(self.medidor_dut.ler_dados())
        self.medidor_std.imprimir_dados(std_readings)
        self.medidor_dut.imprimir_dados(dut_readings)

        for i in range(1,M+1):
        # determina se i é par ou ímpar
        # se i é impar, v_i = 1,01*v_nominal
        # se i é par, v_i = 0,99*v_nominal
            if int(i) % 2 == 0:
                Vi = 0.99*v_nominal;
                self.k.append(-100);
            else:
                Vi = 1.01*v_nominal;
                self.k.append(100);

            self.chave.gpib.write_raw(ac);
            espera(2); # esperar 2 segundos
            self.fonte_dc.gpib.write("OUT +{:.6f} V".format(Vi));
            espera(2); # esperar 2 segundos
            self.chave.gpib.write_raw(dc);
            print("Vdc nominal + 1%: +{:.6f} V".format(Vi));
            # aguarda pelo tempo de espera configurado
            espera(wait_time);
            # lê as saídas de padrão e objeto, e armazena na variável std_readings e
            # dut_readings
            std_readings.append(self.medidor_std.ler_dados())
            dut_readings.append(self.medidor_dut.ler_dados())
            self.medidor_std.imprimir_dados(std_readings)
            self.medidor_dut.imprimir_dados(dut_readings)
                
        # cálculo do n
        self.chave.gpib.write_raw(ac); # mantém chave em ac durante cálculo
        
        if self.medidor_std.modelo == '182A':
            self.X0 = float(std_readings[0].replace('NDCV','').strip())
        else:
            self.X0 = float(std_readings[0].strip())
            
        if self.medidor_dut.modelo == '182A':
            self.Y0 = float(dut_readings[0].replace('NDCV','').strip())
        else:
            self.Y0 = float(dut_readings[0].strip())
        
        del std_readings[0]
        del dut_readings[0]

        if self.medidor_std.modelo == '182A':
            self.Xi = numpy.array([float(a.replace('NDCV','').strip()) for a in std_readings]);
        else:
            self.Xi = numpy.array([float(a.strip()) for a in std_readings]);
            
        if self.medidor_dut.modelo == '182A':    
            self.Yi = numpy.array([float(a.replace('NDCV','').strip()) for a in dut_readings]);
        else:
            self.Yi = numpy.array([float(a.strip()) for a in dut_readings]);
            
        self.nX_array = (self.Xi/self.X0 - 1) * self.k;
        self.nY_array = (self.Yi/self.Y0 - 1) * self.k;

        self.nX_media = numpy.mean(self.nX_array)
        self.nX_desvio = numpy.std(self.nX_array, ddof=1)
        self.nY_media = numpy.mean(self.nY_array)
        self.nY_desvio = numpy.std(self.nY_array, ddof=1)
        
        return

    def equilibrio(self):
        dut_readings = []
        self.fonte_ac.gpib.write("OUT "+str(freq)+" HZ");
        self.fonte_dc.gpib.write("OUT {:.6f} V".format(v_nominal));
        espera(5) # aguarda 5 segundos antes de iniciar equilibrio
        
        # Aplica o valor nominal
        self.chave.gpib.write_raw(dc);
        print("Vdc nominal: +{:.6f} V".format(v_nominal))
        espera(wait_time/2);
        self.fonte_ac.gpib.write("OUT {:.6f} V".format(0.999*v_nominal));
        espera(wait_time/2);
        dut_readings.append(self.medidor_dut.ler_dados())
        self.medidor_dut.imprimir_dados(dut_readings)
        # Aplica Vac - 0.1%
        print("Vac nominal - 0.1%: +{:.6f} V".format(0.999*v_nominal))
        self.chave.gpib.write_raw(ac);
        espera(wait_time)
        dut_readings.append(self.medidor_dut.ler_dados())
        self.medidor_dut.imprimir_dados(dut_readings)
        self.chave.gpib.write_raw(dc);
        espera(2);
        self.fonte_ac.gpib.write("OUT {:.6f} V".format(1.001*v_nominal));
        espera(2);
        # Aplica Vac + 0.1%
        print("Vac nominal + 0.1%: +{:.6f} V".format(1.001*v_nominal))
        self.chave.gpib.write_raw(ac);
        espera(wait_time)
        dut_readings.append(self.medidor_dut.ler_dados())
        self.medidor_dut.imprimir_dados(dut_readings)
        self.chave.gpib.write_raw(dc);
        # cálculo do equilíbrio
        yp = [0.999*v_nominal, 1.001*v_nominal]

        if self.medidor_dut.modelo == '182A':
            xp = [float(dut_readings[1].replace('NDCV','').strip()), float(dut_readings[2].replace('NDCV','').strip())]
            xi = float(dut_readings[0].replace('NDCV','').strip())
        else:
            xp = [float(dut_readings[1].strip()), float(dut_readings[2].strip())]
            xi = float(dut_readings[0].strip())
        # calcula o valor de equilíbrio através de interpolação linear    
        self.vac_atual = numpy.interp(xi,xp,yp);
        self.adj_dc = v_nominal

        if self.vac_atual > 1.1*v_nominal:  # verifica se a tensão AC de equilíbrio não é muito elevada
            raise NameError('Tensão AC ajustada perigosamente alta!')
        
        return

    def medir_acdc(self, ciclo_ac):
        self.vdc_atual = self.adj_dc
        # inicializa arrays de resultados
        std_readings = []
        dut_readings = []
        # configuração da fonte AC
        self.fonte_ac.gpib.write("OUT {:.6f} V".format(self.vac_atual))
        self.fonte_ac.gpib.write("OUT "+str(freq)+" HZ")
        # configuração da fonte DC
        self.fonte_dc.gpib.write("OUT +{:.6f} V".format(self.vdc_atual))
        self.fonte_dc.gpib.write("OUT 0 HZ")
        # Iniciar medição
        espera(2); # esperar 2 segundos
        # Ciclo AC
        # testa se existem dados do último ciclo AC da medição anterior
        if (ciclo_ac == []):
            # caso negativo, medir AC normalmente
            self.chave.gpib.write_raw(ac)
            print("Ciclo AC")
            espera(wait_time);
            # leituras
            std_readings.append(self.medidor_std.ler_dados())
            dut_readings.append(self.medidor_dut.ler_dados())
            self.medidor_std.imprimir_dados(std_readings)
            self.medidor_dut.imprimir_dados(dut_readings)
            self.medidor_std.mostrar_leituras(std_readings,'Ac1')
            self.medidor_dut.mostrar_leituras(dut_readings,'Ac1')

        else:
            # caso positivo, aproveitar as medições do ciclo anterior
            print("Ciclo AC")
            std_readings.append(ciclo_ac[0])
            dut_readings.append(ciclo_ac[1])
            self.medidor_std.imprimir_dados(std_readings)
            self.medidor_dut.imprimir_dados(dut_readings)
            self.medidor_std.mostrar_leituras(std_readings,'Ac1')
            self.medidor_dut.mostrar_leituras(dut_readings,'Ac1')

        # Ciclo DC
        self.chave.gpib.write_raw(dc);
        print("Ciclo +DC")
        espera(wait_time);

        std_readings.append(self.medidor_std.ler_dados())
        dut_readings.append(self.medidor_dut.ler_dados())
        self.medidor_std.imprimir_dados(std_readings)
        self.medidor_dut.imprimir_dados(dut_readings)
        self.medidor_std.mostrar_leituras(std_readings,'Dcp')
        self.medidor_dut.mostrar_leituras(dut_readings,'Dcp')

        # Ciclo AC
        self.chave.gpib.write_raw(ac);
        print("Ciclo AC")
        espera(wait_time/2);
        # Mudar fonte DC para -DC
        self.fonte_dc.gpib.write("OUT -{:.6f} V".format(self.vdc_atual));
        espera(wait_time/2);

        std_readings.append(self.medidor_std.ler_dados())
        dut_readings.append(self.medidor_dut.ler_dados())
        self.medidor_std.imprimir_dados(std_readings)
        self.medidor_dut.imprimir_dados(dut_readings)
        self.medidor_std.mostrar_leituras(std_readings,'Ac2')
        self.medidor_dut.mostrar_leituras(dut_readings,'Ac2')

        # Ciclo -DC
        self.chave.gpib.write_raw(dc);
        print("Ciclo -DC")
        espera(wait_time);

        std_readings.append(self.medidor_std.ler_dados())
        dut_readings.append(self.medidor_dut.ler_dados())
        self.medidor_std.imprimir_dados(std_readings)
        self.medidor_dut.imprimir_dados(dut_readings)
        self.medidor_std.mostrar_leituras(std_readings,'Dcm')
        self.medidor_dut.mostrar_leituras(dut_readings,'Dcm')

        # Ciclo AC
        self.chave.gpib.write_raw(ac);
        print("Ciclo AC")
        espera(wait_time/2);
        # Mudar fonte DC para +DC
        self.fonte_dc.gpib.write("OUT +{:.6f} V".format(self.vdc_atual));
        espera(wait_time/2);

        std_readings.append(self.medidor_std.ler_dados())
        dut_readings.append(self.medidor_dut.ler_dados())
        self.medidor_std.imprimir_dados(std_readings)
        self.medidor_dut.imprimir_dados(dut_readings)
        self.medidor_std.mostrar_leituras(std_readings,'Ac3')
        self.medidor_dut.mostrar_leituras(dut_readings,'Ac3')

        # retorna as leituras obtidas para o objeto e para o padrão
        self.measurements = {'std_readings':std_readings, 'dut_readings':dut_readings}
        return

    def calcular(self):
        # x -> padrao; y -> objeto
        print("Calculando diferença ac-dc...")

        if self.medidor_std.modelo == '182A':
            self.x = numpy.array([float(a.replace('NDCV','').strip()) for a in self.measurements['std_readings']]);
        else:
            self.x = numpy.array([float(a.strip()) for a in self.measurements['std_readings']]);
        # extrai os dados de leitura do objeto

        if self.medidor_dut.modelo == '182A':
            self.y = numpy.array([float(a.replace('NDCV','').strip()) for a in self.measurements['dut_readings']])
        else:
            self.y = numpy.array([float(a.strip()) for a in self.measurements['dut_readings']])
        # calcula Xac, Xdc, Yac e Ydc a partir das leituras brutas    
        Xac = numpy.mean(numpy.array([self.x[0], self.x[2], self.x[4]]));     # AC médio padrão
        Xdc = numpy.mean(numpy.array([self.x[1], self.x[3]]));           # DC médio padrão
        Yac = numpy.mean(numpy.array([self.y[0], self.y[2], self.y[4]]));     # AC médio objeto
        Ydc = numpy.mean(numpy.array([self.y[1], self.y[3]]));           # DC médio objeto
        # Variáveis auxiliares X e Y
        X = Xac/Xdc - 1;
        Y = Yac/Ydc - 1;
        # diferença AC-DC medida:
        self.delta_m = 1e6 * ((X/self.nX_media - Y/self.nY_media)/(1 + Y/self.nY_media));
        # critério para repetir a medição - diferença entre Yac e Ydc

        if self.medidor_dut.modelo == '53132A':
            self.Delta = Yac - Ydc;
        elif self.medidor_dut.modelo == '3458A':
            self.Delta = Yac - Ydc;
        else:
            self.Delta = 1e6 * (Yac - Ydc);

        # ajuste da tensão DC para o próximo ciclo
        self.adj_dc = self.vdc_atual * (1 + (Yac - Ydc)/(self.nY_media * Ydc));
        
        if self.adj_dc > 1.1*v_nominal:
            raise NameError('Tensão DC ajustada perigosamente alta!') 

        # timestamp de cada medição
        date = datetime.datetime.now();
        self.timestamp = datetime.datetime.strftime(date, '%d/%m/%Y %H:%M:%S');
        return

    def interromper(self):
        self.chave.gpib.write_raw(reset);
        espera(1)
        self.fonte_ac.gpib.write("STBY");
        self.fonte_dc.gpib.write("STBY");
        return

    def criar_registro(self):
        date = datetime.datetime.now();
        timestamp_file = datetime.datetime.strftime(date, '%d-%m-%Y_%Hh%Mm');
        timestamp_registro = datetime.datetime.strftime(date, '%d/%m/%Y %H:%M:%S');
        # o nome do registro é criado de forma automática, a partir da data e hora atuais
        self.registro_filename = "registro_"+timestamp_file+".csv"
        
        with open(self.registro_filename,"w") as csvfile:
            registro = csv.writer(csvfile, delimiter=';',lineterminator='\n')
            registro.writerow(['pyAC-DC '+versao]);
            registro.writerow(['Registro de Medições']);
            registro.writerow([' ']);
            registro.writerow(['Início da medição',timestamp_registro]);
            registro.writerow(['Tempo de aquecimento [s]',config['Measurement Config']['aquecimento']]);
            registro.writerow(['Tempo de estabilização [s]',config['Measurement Config']['wait_time']]);
            registro.writerow(['Repetições',config['Measurement Config']['repeticoes']]);
            registro.writerow(['Observações',config['Misc']['observacoes']]);
            registro.writerow([' ']);
            registro.writerow([' ']);
        
        csvfile.close();
        return

    def registrar_frequencia(self):
        with open(self.registro_filename,"a") as csvfile:
            registro = csv.writer(csvfile, delimiter=';',lineterminator='\n')
            registro.writerow(['Tensão [V]',str(v_nominal).replace('.',',')]);
            registro.writerow(['Frequência [kHz]',str(freq / 1000).replace('.',',')]);
            registro.writerow([' ']); 
            registro.writerow(['X0',str(self.X0).replace('.',',')]); 
            registro.writerow(['Xi'] + [str(i).replace('.',',') for i in self.Xi]); 
            registro.writerow(['k'] + [str(i).replace('.',',') for i in self.k]); 
            registro.writerow(['nX'] + [str(i).replace('.',',') for i in self.nX_array]); 
            registro.writerow(['nX (média)',str(self.nX_media).replace('.',',')]); 
            registro.writerow(['nX (desvio padrão)',str(self.nX_desvio).replace('.',',')]); 
            registro.writerow([' ']); 
            registro.writerow(['Y0',str(self.Y0).replace('.',',')]); 
            registro.writerow(['Yi'] + [str(i).replace('.',',') for i in self.Yi]); 
            registro.writerow(['k'] + [str(i).replace('.',',') for i in self.k]); 
            registro.writerow(['nY'] + [str(i).replace('.',',') for i in self.nY_array]); 
            registro.writerow(['nY (média)',str(self.nY_media).replace('.',',')]); 
            registro.writerow(['nY (desvio padrão)',str(self.nY_desvio).replace('.',',')]); 
            registro.writerow([' ']); 
            registro.writerow(['Vac equilíbrio [V]',str(self.vac_atual).replace('.',',')]);
            registro.writerow([' ']); 
            # cabeçalho da tabela de medicao
            registro.writerow(['Data / hora','AC (STD)','AC (DUT)','DC+ (STD)','DC+ (DUT)','AC (STD)','AC (DUT)','DC- (STD)','DC- (DUT)','AC (STD)','AC (DUT)', 'Diferença', 'Delta', 'Tensão DC Aplicada']);
        csvfile.close();
        return

    def registrar_linha(self):

        with open(self.registro_filename,"a") as csvfile:
            registro = csv.writer(csvfile, delimiter=';',lineterminator='\n')
            registro.writerow([self.timestamp,str(self.x[0]).replace('.',','),str(self.y[0]).replace('.',','),str(self.x[1]).replace('.',','),str(self.y[1]).replace('.',','),str(self.x[2]).replace('.',','),str(self.y[2]).replace('.',','),str(self.x[3]).replace('.',','),str(self.y[3]).replace('.',','),str(self.x[4]).replace('.',','),str(self.y[4]).replace('.',','),str(self.delta_m).replace('.',','),str(self.Delta).replace('.',','),str(self.vdc_atual).replace('.',',')]);

        csvfile.close();
        return

    def registrar_media(self,diferenca):

        with open(self.registro_filename,"a") as csvfile:
            registro = csv.writer(csvfile, delimiter=';',lineterminator='\n')
            registro.writerow([' ']);
            registro.writerow(['Média',str(numpy.mean(diferenca)).replace('.',',')]);
            registro.writerow(['Desvio-padrão',str(numpy.std(diferenca, ddof=1)).replace('.',',')]);
            registro.writerow([' ']);
            registro.writerow([' ']);
        csvfile.close();
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
        self.gpibBus.setValue(1)
        self.fonteAcEndereco.setValue(2)
        self.fonteDcEndereco.setValue(6)
        self.medidorStdEndereco.setValue(11)
        self.medidorDutEndereco.setValue(12)
        self.chaveEndereco.setValue(10)

        self.setWindowTitle("Configurações")
        self.resize(800, 400)

    def createLeiturasGroupBox(self):

        self.leiturasGroupBox = QGroupBox("Leituras")

        self.leiturasLabel = {}
        self.leiturasPadrao = {}
        self.leiturasObjeto = {}
  
        for i in ['Ac1','Dcp','Ac2','Dcm','Ac3']:
            self.leiturasLabel[i] = QLabel(self)
            self.leiturasPadrao[i] = QLineEdit(self)
            self.leiturasPadrao[i].setReadOnly(True)
            self.leiturasObjeto[i] = QLineEdit(self)
            self.leiturasObjeto[i].setReadOnly(True)

        self.leiturasLabel['Ac1'].setText(" AC")
        self.leiturasLabel['Dcp'].setText("+DC")
        self.leiturasLabel['Ac2'].setText(" AC")
        self.leiturasLabel['Dcm'].setText("-DC")
        self.leiturasLabel['Ac3'].setText(" AC")

        # padrao
        self.leiturasPadraoLabel = QLabel(self)
        self.leiturasPadraoLabel.setText("Padrão [mV]")

        # objeto
        self.leiturasObjetoLabel = QLabel(self)
        self.leiturasObjetoLabel.setText("Objeto [mV]")

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

        j = 1
        for i in ['Ac1','Dcp','Ac2','Dcm','Ac3']:
            leiturasGroupBoxLayout.addWidget(self.leiturasLabel[i], j, 0)
            leiturasGroupBoxLayout.addWidget(self.leiturasPadrao[i], j, 1)
            leiturasGroupBoxLayout.addWidget(self.leiturasObjeto[i], j, 2)
            j += 1
        
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
        global AC
        global DC
        global STD
        global DUT
        global SW
        if checkbox.isChecked():
            try:
                if checkbox.text() == "Fonte AC":
                    AC = Fonte(str(self.gpibBus.value()),str(self.fonteAcEndereco.value()),self.fonteAcModelo.currentText(),'AC')
                    self.fonteAcIdn.setText(AC.idn)
                elif checkbox.text() == "Fonte DC":
                    DC = Fonte(str(self.gpibBus.value()),str(self.fonteDcEndereco.value()),self.fonteDcModelo.currentText(),'DC')
                    self.fonteDcIdn.setText(DC.idn)
                elif checkbox.text() == "Medidor do Padrão":
                    STD = Medidor(str(self.gpibBus.value()),str(self.medidorStdEndereco.value()),self.medidorStdModelo.currentText(),'STD')
                    self.medidorStdIdn.setText(STD.idn)
                elif checkbox.text() == "Medidor do Objeto":
                    DUT = Medidor(str(self.gpibBus.value()),str(self.medidorDutEndereco.value()),self.medidorDutModelo.currentText(),'DUT')
                    self.medidorDutIdn.setText(DUT.idn)
                elif checkbox.text() == "Chave AC/DC":
                    SW = Chave(str(self.gpibBus.value()),str(self.chaveEndereco.value()),self.chaveModelo.currentText())
                    self.chaveIdn.setText(SW.idn)
                return
                    
            except:
                QMessageBox.critical(self, "Erro",
                "Erro ao conectar com o instrumento!",
                QMessageBox.Abort)
                
        else:
            try:
                if checkbox.text() == "Fonte AC":
                    AC.gpib.control_ren(0)
                    self.fonteAcIdn.setText("")
                elif checkbox.text() == "Fonte DC":
                    DC.gpib.control_ren(0)
                    self.fonteDcIdn.setText("")
                elif checkbox.text() == "Medidor do Padrão":
                    STD.gpib.control_ren(0)
                    self.medidorStdIdn.setText.setText("")
                elif checkbox.text() == "Medidor do Objeto":
                    DUT.gpib.control_ren(0)
                    self.medidorDutIdn.setText("")
                elif checkbox.text() == "Chave AC/DC":
                    SW.gpib.control_ren(0)
                    self.chaveIdn.setText("")
                return
            except:
                #QMessageBox.critical(self, "Erro",
                #"Erro ao conectar com o instrumento!",
                #QMessageBox.Abort)
                self.chaveIdn.setText("")
        return
            

    def createButtonsLayout(self):
##        self.newScreenshotButton = self.createButton("New Screenshot",
##                self.newScreenshot)
##
##        self.saveScreenshotButton = self.createButton("Save Screenshot",
##                self.saveScreenshot)

        self.quitConfig = self.createButton("Sair", self.close)
        self.medir = self.createButton("Medir", self.iniciarMedicao)
        self.parar = self.createButton("Parar", self.pararMedicao)

        self.buttonsLayout = QHBoxLayout()
        self.buttonsLayout.addStretch()
        self.buttonsLayout.addWidget(self.medir)
        self.buttonsLayout.addWidget(self.parar)
        self.buttonsLayout.addWidget(self.quitConfig)

    def createButton(self, text, member):
        button = QPushButton(text)
        button.clicked.connect(member)
        return button

    def pararMedicao(self):
        try:
            self.setup.interromper()
        except:
            QMessageBox.critical(self, "Erro",
                "A medição não foi iniciada!",
                QMessageBox.Abort)

    def iniciarMedicao2(self):
        global v_nominal
        global AC
        global DC
        global STD
        global DUT
        global SW
        print(AC.idn)
        print(DC.idn)
        print(STD.idn)
        print(DUT.idn)
        print(SW.idn)
        setup = Medicao(AC, DC, STD, DUT, SW)
        print(AC.gpib.query("*IDN?"))
        v_nominal = float(self.voltage.text().strip())
        print(v_nominal)
        setup.inicializar()
        
        return
    
    def iniciarMedicao(self):
        global AC
        global DC
        global STD
        global DUT
        global SW

        global freq
        global freq_array
        global v_nominal
        global repeticoes
        global wait_time
        global heating_time
                    
        freq_array = self.frequency.text().split(',')
        v_nominal = float(self.voltage.text().strip())
        repeticoes = int(self.repeticoes.value())
        wait_time = int(self.waitTime.value())
        heating_time = int(self.repeticoesAquecimento.value())

        self.repeticoesTotal.setText(str(repeticoes))
        self.esperaTotal.setText(str(wait_time))
##        except:
##            QMessageBox.critical(self, "Erro",
##                "Os instrumentos não foram inicializados!",
##                QMessageBox.Abort)
##        else:
        try:
            # mostrar repeticoes e espera na interface gráfica

            
            setup = Medicao(AC, DC, STD, DUT, SW)

            print("Colocando fontes em OPERATE...")

            setup.inicializar()
            print("Criando arquivo de registro...")
            setup.criar_registro()

            print("Arquivo "+setup.registro_filename+" criado com sucesso!")

            print("Tempo de aquecimento: "+str(heating_time)+" s")
            print("Iniciando o aquecimento.")
            setup.aquecimento(heating_time)  # inicia o aquecimento
                    
            # fazer loop para cada valor de frequencia
            for value in freq_array:
                freq = float(value) * 1000;

                print("Iniciando a medição...")
                print("V nominal: {:5.2f} V, f nominal: {:5.2f} Hz".format(v_nominal,freq));

                print("Medindo o N...")
                setup.medir_n(4)       # 4 repetições para o cálculo do N
                        
                print("N STD (média): {:5.2f}".format(setup.nX_media))
                print("N STD (desvio padrão): {:5.2f}".format(setup.nX_desvio))
                print("N DUT (média): {:5.2f}".format(setup.nY_media))
                print("N DUT (desvio padrão): {:5.2f}".format(setup.nY_desvio))

                # mostrar o valor do n na interface
                self.nPadrao.setText("{:5.2f}".format(setup.nX_media))
                self.nObjeto.setText("{:5.2f}".format(setup.nY_media))

                print("Equilibrio AC...")
                setup.equilibrio()
                        
                print("Vac aplicado: {:5.6f} V".format(setup.vac_atual))
                        
                setup.registrar_frequencia()     # inicia o registro para a frequencia atual
                        
                print("Iniciando medição...");
                first_measure = True;            # flag primeira repeticao
                diff_acdc = [];
                Delta = [];
                        
                i = 0;
                while (i < repeticoes):  # inicia as repetições da medição

                    print ("Vdc aplicado: {:5.6f} V".format(setup.adj_dc))

                    if first_measure:    # testa se é a primeira medição
                        ciclo_ac = [];
                        first_measure = False
                    else:
                        ciclo_ac = [setup.measurements['std_readings'][4], setup.measurements['dut_readings'][4]];  # caso não seja, aproveitar o último ciclo AC

                    setup.medir_acdc(ciclo_ac)       # ciclo de medicao
                    setup.calcular()                 # calcula da diferenca ac-dc

                    print("Diferença ac-dc: {:5.2f}".format(setup.delta_m))               
                    print("Delta: {:5.2f}".format(setup.Delta))
                    print("Data / hora: "+setup.timestamp);

                    if abs(setup.Delta) > 1:               # se o ponto não passa no critério de descarte, repetir medição
                        print("Delta > 1. Ponto descartado!")
                    else:
                        diff_acdc.append(setup.delta_m)
                        Delta.append(setup.Delta)
                        setup.registrar_linha()
                        i += 1;

                    for i in ['Ac1','Dcp','Ac2','Dcm','Ac3']:
                        self.leiturasPadrao[i].setText("")
                        self.leiturasObjeto[i].setText("")
                                
                print("Medição concluída.")                      
                        
                print("Resultados:")
                print("Média: {:5.2f}".format(numpy.mean(diff_acdc)))
                print("Desvio padrão: {:5.2f}".format(numpy.std(diff_acdc, ddof=1)))
                print("Salvando arquivo...")
                registrar_media(diff_acdc)

                setup.interromper()
                print("Concluído.")
                    
        except:
            self.setup.interromper()
            import traceback
            traceback.print_exc()
 

if __name__ == '__main__':

    import sys

    app = QApplication(sys.argv)
    configuracoes = Configuracoes()
    configuracoes.show()
    sys.exit(app.exec_())
