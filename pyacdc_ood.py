# pyAC-DC.py
# Programa para a medição de diferença AC-DC em conversores térmicos (TCs)
# O programa aceita TCs com saída em tensão, frequência e resistência.
#-------------------------------------------------------------------------------
# Autor:       Gean Marcos Geronymo
#
# Versão inicial:      10-Jun-2016
# Última modificação:  11-Jan-2017
#
# Jan/2017: Programa reestruturado para orientação à objetos.
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
# Nomenclatura de variáveis:
#
# Adotou-se a convenção de utilizar X para as variáveis referentes ao padrão
# e Y para as variáveis referentes ao objeto.
#
# Por exemplo:
#
# Xac - leitura do padrão (std) quando submetido a Vac
# Xdc - leitura do padrão (std) quando submetido a Vdc
# Yac - leitura do objeto (dut) quando submetido a Vac
# Ydc - leitura do objeto (dut) quando submetido a Vdc
#
# O instrumento que lê a saída do padrão é identificado
# como 'STD' e o instrumento que lê a saída do objeto
# como 'DUT'.
#
# Comandos da chave
# os comandos sao enviados em formato ASCII puro
# utilizar os comandos
# sw.write_raw(chr(2)) (reset)
# sw.write_raw(chr(4)) (ac)
# sw.write_raw(chr(6)) (dc)
# chr(argumento) converte o valor binario em ascii
#-------------------------------------------------------------------------------
# versão do programa
versao = '0.5';
#-------------------------------------------------------------------------------
# Carregar módulos
import visa
import datetime
import configparser
import time
import numpy
import datetime
import csv
# classes abstratas:
from abc import ABCMeta, abstractmethod
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
# Constantes e variáveis globais
# comandos da chave (em ASCII puro)
reset = chr(2)
ac = chr(4)
dc = chr(6)
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
# Configurações
#-------------------------------------------------------------------------------
# o arquivo settings.ini reune as configurações que podem ser alteradas
config = configparser.ConfigParser() # iniciar o objeto config
config.read('config_ood.ini') # ler o arquivo de configuracao
wait_time = int(config['Measurement Config']['wait_time']); # tempo de espera
heating_time = int(config['Measurement Config']['aquecimento']); # tempo de aquecimento
rm = visa.ResourceManager()
repeticoes = int(config['Measurement Config']['repeticoes']); # quantidade de repetições
v_nominal = float(config['Measurement Config']['voltage']); # Tensão nominal 
freq_array = config['Measurement Config']['frequency'].split(',') # Array com as frequências
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
# Funções globais
#-------------------------------------------------------------------------------
# função espera(segundos)
# aceita como parâmetro o tempo de espera, em segundos
# hack para poder interromper o programa a qualquer momento
# no Windows XP, a função time.sleep não pode ser interrompida por uma
# interrupção de teclado. A função quebra a chamada dessa função em várias
# chamadas de 0,1 segundo.

def espera(segundos):
    for i in range(int(segundos * 10)):
        time.sleep(0.1)    
    return

#-------------------------------------------------------------------------------
# Classes
#-------------------------------------------------------------------------------

class Instrumento(object):
    """ Classe genérica para os instrumentos
    Atributos:
    endereco: string com o endereço GPIB do instrumento
    modelo: modelo do instrumento
    """

    __metaclass__ = ABCMeta
    def __init__(self, endereco, modelo):
        self.endereco = endereco
        self.resource = rm.open_resource("GPIB0::"+self.endereco+"::INSTR")
        self.modelo = modelo

#-------------------------------------------------------------------------------
        
class Chave(Instrumento):
    """ Classe para a chave AC-DC
    Atributos:
    endereco: string com o endereço GPIB do instrumento
    modelo: modelo do instrumento ('METAS')
    """

    def __init__(self):
        Instrumento.__init__(self,config['GPIB']['SW'],'METAS')
    
    def print_idn(self):
        print("Comunicando com a chave no endereço "+self.endereco+".");
        print("reset");
        self.resource.write_raw(reset);
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
    def __init__(self, tipo):
        Instrumento.__init__(self, config['GPIB'][tipo], config['Instruments'][tipo])
        self.tipo = tipo
        self.idn = self.resource.query("*IDN?"));

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
            self.resource.write("OFORMAT ASCII")
            self.resource.write("END ALWAYS")
            self.resource.write("NPLC 8")
            self.idn = self.resource.query("ID?"));
            
        elif self.modelo == '182A':
            self.resource.write("R0I0B1X")
            self.resource.write("S2N1X")
            self.resource.write("O1P2X")
            self.idn = "Keithley 182A"

        elif self.modelo == '53132A':
            self.idn = self.resource.query("*IDN?"));
            self.resource.write("*RST")
            self.resource.write("*CLS")
            self.resource.write("*SRE 0")
            self.resource.write("*ESE 0")
            self.resource.write(":STAT:PRES")
            # comandos para throughput máximo
            self.resource.write(":FORMAT ASCII")
            self.resource.write(":FUNC 'FREQ 1'")
            self.resource.write(":EVENT1:LEVEL 0")
            # configura o gate size (1 s)
            self.resource.write(":FREQ:ARM:STAR:SOUR IMM")
            self.resource.write(":FREQ:ARM:STOP:SOUR TIM")
            self.resource.write(":FREQ:ARM:STOP:TIM 1")
            # configura para utilizar oscilador interno
            self.resource.write(":ROSC:SOUR INT")
            # desativa interpolador automatico
            self.resource.write(":DIAG:CAL:INT:AUTO OFF")
            # desativa todo o pós-processamento
            self.resource.write(":CALC:MATH:STATE OFF")
            self.resource.write(":CALC2:LIM:STATE OFF")
            self.resource.write(":CALC3:AVER:STATE OFF")
            self.resource.write(":HCOPY:CONT OFF")
            self.resource.write("*DDT #15FETC?")
            self.resource.write(":INIT:CONT ON")

        elif self.modelo == '2182A':
            self.resource.write("SENS:CHAN 2")
            self.resource.write(":SENS:VOLT:CHAN2:RANG:AUTO ON")
            self.resource.write(":SENS:VOLT:NPLC 18")
            self.resource.write(":SENS:VOLT:DIG 8")
            self.idn = self.resource.query("*IDN?"));
            
        else:
            self.idn = self.resource.query("*IDN?"));
        
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
            x = self.resource.query("X")
        elif self.modelo == '2182A':
            x = self.resource.query(":FETCH?")
        elif self.modelo == '53132A':
            x = self.resource.query(":FETCH:FREQ?")
        elif self.modelo == '3458A':
            x = self.resource.query("OHM 100E3")
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

#-------------------------------------------------------------------------------
    
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
        # configuração da fonte AC
        self.fonte_ac.write("OUT +{:.6f} V".format(v_nominal));
        self.fonte_ac.write("OUT 1000 HZ");
        # configuração da fonte DC
        self.fonte_dc.write("OUT +{:.6f} V".format(v_nominal));
        self.fonte_dc.write("OUT 0 HZ");
        # Entrar em OPERATE
        espera(2); # esperar 2 segundos
        self.fonte_ac.write("*CLS");
        self.fonte_ac.write("OPER");
        self.fonte_dc.write("*CLS");
        self.fonte_dc.write("OPER");
        espera(10);
        self.chave.write_raw(ac);
        espera(10);

    def aquecimento(self, tempo):
    # executa o aquecimento, mantendo a tensão nominal aplicada pelo tempo
    # (em segundos) definido na variavel "tempo", alternando entre AC e DC
    # a cada 60 segundos
        rep = int(tempo / 120);
        self.fonte_dc.write("OUT +{:.6f} V".format(v_nominal));
        self.fonte_dc.write("OUT 0 HZ");
        self.fonte_ac.write("OUT +{:.6f} V".format(v_nominal));
        self.fonte_ac.write("OUT 1000 HZ");

        for i in range(1,rep):
            self.chave.write_raw(dc);
            espera(60);
            self.chave.write_raw(ac);
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
        self.fonte_ac.write("OUT {:.6f} V".format(v_nominal));
        self.fonte_ac.write("OUT "+str(freq)+" HZ");
        self.fonte_dc.write("OUT +{:.6f} V".format(v_nominal));
        espera(2); # espera 2 segundos
        self.chave.write_raw(dc);
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

            self.chave.write_raw(ac);
            espera(2); # esperar 2 segundos
            self.fonte_dc.write("OUT +{:.6f} V".format(Vi));
            espera(2); # esperar 2 segundos
            self.chave.write_raw(dc);
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
        self.chave.write_raw(ac); # mantém chave em ac durante cálculo
        
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
            
        self.nX = (Xi/X0 - 1) * k;
        self.nY = (Yi/Y0 - 1) * k;

        self.results_n = [numpy.mean(nX), numpy.std(nX, ddof=1), numpy.mean(nY), numpy.std(nY, ddof=1)];

        return

    def equilibrio(self):
        dut_readings = []
        self.fonte_ac.write("OUT "+str(freq)+" HZ");
        self.fonte_dc.write("OUT {:.6f} V".format(v_nominal));
        espera(5) # aguarda 5 segundos antes de iniciar equilibrio
        
        # Aplica o valor nominal
        self.chave.write_raw(dc);
        print("Vdc nominal: +{:.6f} V".format(v_nominal))
        espera(wait_time/2);
        self.fonte_ac.write("OUT {:.6f} V".format(0.999*v_nominal));
        espera(wait_time/2);
        dut_readings.append(self.medidor_dut.ler_dados())
        self.medidor_dut.imprimir_dados(dut_readings)
        # Aplica Vac - 0.1%
        print("Vac nominal - 0.1%: +{:.6f} V".format(0.999*v_nominal))
        self.chave.write_raw(ac);
        espera(wait_time)
        dut_readings.append(self.medidor_dut.ler_dados())
        self.medidor_dut.imprimir_dados(dut_readings)
        self.chave.write_raw(dc);
        espera(2);
        self.fonte_ac.write("OUT {:.6f} V".format(1.001*v_nominal));
        espera(2);
        # Aplica Vac + 0.1%
        print("Vac nominal + 0.1%: +{:.6f} V".format(1.001*v_nominal))
        self.chave.write_raw(ac);
        espera(wait_time)
        dut_readings.append(self.medidor_dut.ler_dados())
        self.medidor_dut.imprimir_dados(dut_readings)
        self.chave.write_raw(dc);
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

        if vac_atual > 1.1*v_nominal:  # verifica se a tensão AC de equilíbrio não é muito elevada
            raise NameError('Tensão AC ajustada perigosamente alta!')
        
        # retorna o novo valor de AC
        # return new_ac
        return

    def medir_acdc(self, ciclo_ac):
        self.vdc_atual = self.adj_dc
        # inicializa arrays de resultados
        std_readings = []
        dut_readings = []
        # configuração da fonte AC
        self.fonte_ac.write("OUT {:.6f} V".format(self.vac_atual))
        self.fonte_ac.write("OUT "+str(freq)+" HZ")
        # configuração da fonte DC
        self.fonte_dc.write("OUT +{:.6f} V".format(self.vdc_atual))
        self.fonte_dc.write("OUT 0 HZ")
        # Iniciar medição
        espera(2); # esperar 2 segundos
        # Ciclo AC
        # testa se existem dados do último ciclo AC da medição anterior
        if (ciclo_ac == []):
            # caso negativo, medir AC normalmente
            self.chave.write_raw(ac)
            print("Ciclo AC")
            espera(wait_time);
            # leituras
            std_readings.append(self.medidor_std.ler_dados())
            dut_readings.append(self.medidor_dut.ler_dados())
            self.medidor_std.imprimir_dados(std_readings)
            self.medidor_dut.imprimir_dados(dut_readings)

        else:
            # caso positivo, aproveitar as medições do ciclo anterior
            print("Ciclo AC")
            std_readings.append(ciclo_ac[0])
            dut_readings.append(ciclo_ac[1])
            self.medidor_std.imprimir_dados(std_readings)
            self.medidor_dut.imprimir_dados(dut_readings)

        # Ciclo DC
        self.chave.write_raw(dc);
        print("Ciclo +DC")
        espera(wait_time);

        std_readings.append(self.medidor_std.ler_dados())
        dut_readings.append(self.medidor_dut.ler_dados())
        self.medidor_std.imprimir_dados(std_readings)
        self.medidor_dut.imprimir_dados(dut_readings)

        # Ciclo AC
        self.chave.write_raw(ac);
        print("Ciclo AC")
        espera(wait_time/2);
        # Mudar fonte DC para -DC
        self.fonte_dc.write("OUT -{:.6f} V".format(vdc_atual));
        espera(wait_time/2);

        std_readings.append(self.medidor_std.ler_dados())
        dut_readings.append(self.medidor_dut.ler_dados())
        self.medidor_std.imprimir_dados(std_readings)
        self.medidor_dut.imprimir_dados(dut_readings)

        # Ciclo -DC
        self.chave.write_raw(dc);
        print("Ciclo -DC")
        espera(wait_time);

        std_readings.append(self.medidor_std.ler_dados())
        dut_readings.append(self.medidor_dut.ler_dados())
        self.medidor_std.imprimir_dados(std_readings)
        self.medidor_dut.imprimir_dados(dut_readings)

        # Ciclo AC
        self.chave.write_raw(ac);
        print("Ciclo AC")
        espera(wait_time/2);
        # Mudar fonte DC para +DC
        self.fonte_dc.write("OUT +{:.6f} V".format(vdc_atual));
        espera(wait_time/2);

        std_readings.append(self.medidor_std.ler_dados())
        dut_readings.append(self.medidor_dut.ler_dados())
        self.medidor_std.imprimir_dados(std_readings)
        self.medidor_dut.imprimir_dados(dut_readings)

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
        Xac = numpy.mean(numpy.array([x[0], x[2], x[4]]));     # AC médio padrão
        Xdc = numpy.mean(numpy.array([x[1], x[3]]));           # DC médio padrão
        Yac = numpy.mean(numpy.array([y[0], y[2], y[4]]));     # AC médio objeto
        Ydc = numpy.mean(numpy.array([y[1], y[3]]));           # DC médio objeto
        # Variáveis auxiliares X e Y
        X = Xac/Xdc - 1;
        Y = Yac/Ydc - 1;
        # diferença AC-DC medida:
        self.delta_m = 1e6 * ((X/self.n_X - Y/self.n_Y)/(1 + Y/self.n_Y));
        # critério para repetir a medição - diferença entre Yac e Ydc

        if self.medidor_dut.modelo == '53132A':
            self.Delta = Yac - Ydc;
        elif self.medidor_dut.modelo == '3458A':
            self.Delta = Yac - Ydc;
        else:
            self.Delta = 1e6 * (Yac - Ydc);

        # ajuste da tensão DC para o próximo ciclo
        self.adj_dc = self.vdc_atual * (1 + (Yac - Ydc)/(self.n_Y * Ydc));
        
        if self.adj_dc > 1.1*v_nominal:
            raise NameError('Tensão DC ajustada perigosamente alta!') 

        # timestamp de cada medição
        date = datetime.datetime.now();
        self.timestamp = datetime.datetime.strftime(date, '%d/%m/%Y %H:%M:%S');
        return

    def interromper(self):
        self.chave.write_raw(reset);
        espera(1)
        self.fonte_ac.write("STBY");
        self.fonte_dc.write("STBY");
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
            registro.writerow(['nX'] + [str(i).replace('.',',') for i in self.nX]); 
            registro.writerow(['nX (média)',str(self.results_n[0]).replace('.',',')]); 
            registro.writerow(['nX (desvio padrão)',str(self.results_n[1]).replace('.',',')]); 
            registro.writerow([' ']); 
            registro.writerow(['Y0',str(self.Y0).replace('.',',')]); 
            registro.writerow(['Yi'] + [str(i).replace('.',',') for i in self.Yi]); 
            registro.writerow(['k'] + [str(i).replace('.',',') for i in self.k]); 
            registro.writerow(['nY'] + [str(i).replace('.',',') for i in self.nY]); 
            registro.writerow(['nY (média)',str(self.results_n[2]).replace('.',',')]); 
            registro.writerow(['nY (desvio padrão)',str(self.results_n[3]).replace('.',',')]); 
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
            registro.writerow(self.timestamp,str(self.x[0]).replace('.',','),str(self.y[0]).replace('.',','),str(self.x[1]).replace('.',','),str(self.y[1]).replace('.',','),str(self.x[2]).replace('.',','),str(self.y[2]).replace('.',','),str(self.x[3]).replace('.',','),str(self.y[3]).replace('.',','),str(self.x[4]).replace('.',','),str(self.y[4]).replace('.',','),str(self.delta_m).replace('.',','),str(self.Delta).replace('.',','),str(self.vdc_atual).replace('.',',')]);

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
    
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
# Programa principal
#-------------------------------------------------------------------------------
def main():
    try:
        global freq;
        print("Inicializando os intrumentos...")

        # inicializacao dos objetos
        AC = Fonte('AC')
        DC = Fonte('DC')
        STD = Medidor('STD')
        DUT = Medidor('DUT')
        SW = Chave()
        
        # inicializacao do objeto Measurement
        print("Colocando fontes em OPERATE...")
        setup = Medicao(AC, DC, STD, DUT, SW)
        
        
        print("Criando arquivo de registro...")
        setup.criar_registro()

        print("Arquivo "+setup.registro_filename+" criado com sucesso!")

        print("Aquecimento...")
        setup.aquecimento(heating_time)  # inicia o aquecimento
        
        # fazer loop para cada valor de frequencia
        for value in freq_array:
            freq = float(value) * 1000;

            print("Iniciando a medição...")
            print("V nominal: {:5.2f} V, f nominal: {:5.2f} Hz".format(v_nominal,freq));

            print("Medindo o N...")
            setup.medir_n(4)       # 4 repetições para o cálculo do N
            
            print("N STD (média): {:5.2f}".format(setup.results_n[0]))
            print("N STD (desvio padrão): {:5.2f}".format(setup.results_n[1]))
            print("N DUT (média): {:5.2f}".format(setup.results_n[2]))
            print("N DUT (desvio padrão): {:5.2f}".format(setup.results_n[3]))   

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
                    
            print("Medição concluída.")                      
        
            print("Resultados:")
            print("Média: {:5.2f}".format(numpy.mean(diff_acdc)))
            print("Desvio padrão: {:5.2f}".format(numpy.std(diff_acdc, ddof=1)))
            print("Salvando arquivo...")
            registrar_media(diff_acdc)

        setup.interromper()
        print("Concluído.")
                
    except:
        setup.interromper()
        import traceback
        traceback.print_exc()
        

# execução do programa principal
if __name__ == '__main__':
    main()
