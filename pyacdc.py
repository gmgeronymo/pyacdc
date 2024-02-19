# pyAC-DC.py
# Programa para a medição de diferença AC-DC em conversores térmicos (TCs)
# O programa aceita TCs com saída em tensão, frequência e resistência.
#-------------------------------------------------------------------------------
# Autor:       Gean Marcos Geronymo
#
# Versão inicial:      10-Jun-2016
# Última modificação:  25-Jul-2022
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
# como 'std' e o instrumento que lê a saída do objeto
# como 'dut'.
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
import pyvisa as visa
import datetime
import configparser
import time
import numpy
import datetime
import csv
# condicoes ambientais - bme280
import smbus2
import bme280
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
config.read('config.ini') # ler o arquivo de configuracao
wait_time = int(config['Measurement Config']['wait_time']); # tempo de espera
heating_time = int(config['Measurement Config']['aquecimento']); # tempo de aquecimento
rm = visa.ResourceManager('@py')
repeticoes = int(config['Measurement Config']['repeticoes']); # quantidade de repetições
vac_nominal = float(config['Measurement Config']['voltage']); # Tensão nominal AC
vdc_nominal = float(config['Measurement Config']['voltage']); # Tensão nominal DC
freq_array = config['Measurement Config']['frequency'].split(',') # Array com as frequências
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
# Definições das funções
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
# inicializar bme280
def bme280_init():
    global port;
    port = 1;
    global address;
    address = 0x76;
    global bus;
    bus = smbus2.SMBus(port);
    global calibration_params;
    calibration_params = bme280.load_calibration_params(bus, address)

    return

def bme280_read():
    return bme280.sample(bus, address, calibration_params)

# função instrument_init()
# inicializa a comunicação com os instrumentos, via GPIB
def instrument_init():
    # variáveis globais
    global ac_source;
    global dc_source;
    global std;
    global dut;
    global sw;
    # Inicialização dos intrumentos conectados ao barramento GPIB
    print("Comunicando com fonte AC no endereço "+config['GPIB']['ac_source']+"...");
    ac_source = rm.open_resource("GPIB0::"+config['GPIB']['ac_source']+"::INSTR");
    print(ac_source.query("*IDN?"));
    print("OK!\n");

    print("Comunicando com fonte DC no endereço "+config['GPIB']['dc_source']+"...");
    dc_source = rm.open_resource("GPIB0::"+config['GPIB']['dc_source']+"::INSTR");
    print(dc_source.query("*IDN?"));
    print("OK!\n");

    print("Comunicando com o medidor do padrão no endereço "+config['GPIB']['std']+"...");
    std = rm.open_resource("GPIB0::"+config['GPIB']['std']+"::INSTR");
    
    if config['Instruments']['std'] == '3458A':
        std.write("OFORMAT ASCII")
        std.write("END ALWAYS")
        std.write("NPLC 8")
        print(std.query("ID?"))
        print("OK!\n");
    elif config['Instruments']['std'] == '182A':
        # query dividida para evitar timeout
        # R0 = enable autorange
        # I0 = disable buffer
        # B1 = 6 1/2 digit resolution
        # S2 = periodo de integracao: 100 ms
        # N1 = filters on
        # O1 = analog filter on
        # P2 = digital filter medium response
        std.write("X")
        #std.write("R0I0B1S2N1O1P2X")
        std.write("R0I0B1X")
        #std.write("S2N1X")
        std.write("O1P2X")
        print("Keithley 182A...\n")
        print("OK!\n");
    elif config['Instruments']['std'] == '53132A':
        print(std.query("*IDN?"));
        counter_init(std);
        print("OK!\n");
    elif config['Instruments']['std'] == '2182A':
        std.write("SENS:CHAN 1")
        std.write(":SENS:VOLT:CHAN1:RANG:AUTO ON")
        std.write(":SENS:VOLT:NPLC 18")
        std.write(":SENS:VOLT:DIG 8")
        print(std.query("*IDN?"));
        print("OK!\n");
    else:
        print(std.query("*IDN?"));
        print("OK!\n");

    print("Comunicando com o medidor do objeto no endereço "+config['GPIB']['dut']+"...");
    dut = rm.open_resource("GPIB0::"+config['GPIB']['dut']+"::INSTR");

    if config['Instruments']['dut'] == '3458A':
        dut.write("OFORMAT ASCII")
        dut.write("END ALWAYS")
        dut.write("NPLC 8")
        print(dut.query("ID?"))
        print("OK!\n");
    elif config['Instruments']['dut'] == '182A':
        dut.write("X")
        dut.write("R0I0B1X")
        #dut.write("S2N1X")
        dut.write("O1P2X")
        print("Keithley 182A...\n")
        print("OK!\n");
    elif config['Instruments']['dut'] == '53132A':
        print(dut.query("*IDN?"));
        counter_init(dut);
        print("OK!\n");
    elif config['Instruments']['dut'] == '2182A':
        dut.write("SENS:CHAN 1")
        dut.write(":SENS:VOLT:CHAN1:RANG:AUTO ON")
        dut.write(":SENS:VOLT:NPLC 18")
        dut.write(":SENS:VOLT:DIG 8")
        print(dut.query("*IDN?"));
        print("OK!\n");
    else:
        print(dut.query("*IDN?"));
        print("OK!\n");

    print("Comunicando com a chave no endereço "+config['GPIB']['sw']+"...");
    sw = rm.open_resource("GPIB0::"+config['GPIB']['sw']+"::INSTR");
    sw.write_raw(reset);
    print("OK!\n");

    return
#-------------------------------------------------------------------------------
# funcao counter_init()
# envia os comandos para inicializar o contador Agilent 53132A
def counter_init(instrumento):
    instrumento.write("*RST")
    instrumento.write("*CLS")
    instrumento.write("*SRE 0")
    instrumento.write("*ESE 0")
    instrumento.write(":STAT:PRES")
    # comandos para throughput máximo
    instrumento.write(":FORMAT ASCII")
    instrumento.write(":FUNC 'FREQ 1'")
    instrumento.write(":EVENT1:LEVEL 0")
    # configura o gate size (1 s)
    instrumento.write(":FREQ:ARM:STAR:SOUR IMM")
    instrumento.write(":FREQ:ARM:STOP:SOUR TIM")
    instrumento.write(":FREQ:ARM:STOP:TIM 1")
    # configura para utilizar oscilador interno
    instrumento.write(":ROSC:SOUR INT")
    # desativa interpolador automatico
    instrumento.write(":DIAG:CAL:INT:AUTO OFF")
    # desativa todo o pós-processamento
    instrumento.write(":CALC:MATH:STATE OFF")
    instrumento.write(":CALC2:LIM:STATE OFF")
    instrumento.write(":CALC3:AVER:STATE OFF")
    instrumento.write(":HCOPY:CONT OFF")
    instrumento.write("*DDT #15FETC?")
    instrumento.write(":INIT:CONT ON")
    return
#-------------------------------------------------------------------------------
# função meas_init()
# inicializa os instrumentos, coloca as fontes em OPERATE, etc.
def meas_init():
    # configuração da fonte AC
    ac_source.write("OUT +{:.6f} V".format(vac_nominal));
    ac_source.write("OUT 1000 HZ");
    # configuração da fonte DC
    dc_source.write("OUT +{:.6f} V".format(vdc_nominal));
    dc_source.write("OUT 0 HZ");
    # AC-AC
    #dc_source.write("OUT 1000 HZ");
    # Entrar em OPERATE
    espera(2); # esperar 2 segundos
    ac_source.write("*CLS");
    ac_source.write("OPER");
    dc_source.write("*CLS");
    dc_source.write("OPER");
    espera(10);
    sw.write_raw(ac);
    espera(10);
    return
#-------------------------------------------------------------------------------
# função ler_std()
# retorna uma leitura single-shot da saída do TC padrão
# não aceita parâmetros de entrada
def ler_std():
    if config['Instruments']['std'] == '182A':
        x = std.query("X")
    elif config['Instruments']['std'] == '2182A':
        x = std.query(":FETCH?")
    elif config['Instruments']['std'] == '53132A':
        x = std.query(":FETCH:FREQ?")
    elif config['Instruments']['std'] == '3458A':
        x = std.query("OHM 100E3")
    return x
#-------------------------------------------------------------------------------
# função ler_std()
# retorna uma leitura single-shot da saída do TC objeto
# não aceita parâmetros de entrada
def ler_dut():
    if config['Instruments']['dut'] == '182A':
        x = dut.query("X")
    elif config['Instruments']['dut'] == '2182A':
        x = dut.query(":FETCH?")
    elif config['Instruments']['dut'] == '53132A':
        x = dut.query(":FETCH:FREQ?")
    elif config['Instruments']['dut'] == '3458A':
        x = dut.query("OHM 100E3")
    return x
#-------------------------------------------------------------------------------
# função ler_std()
# aceita como parâmetro o vetor com as leituras do padrão
# escreve na tela a última leitura da saída do TC padrão
def print_std(std_readings):
    if config['Instruments']['std'] == '182A':
        print("STD [mV] {:5.6f}".format(float(std_readings[-1].replace('NDCV','').strip())*1000)) 
    elif config['Instruments']['std'] == '2182A':
        print("STD [mV] {:5.6f}".format(float(std_readings[-1].strip())*1000))
    elif config['Instruments']['std'] == '53132A':
        print("STD [Hz] {:5.8f}".format(float(std_readings[-1].strip())))
    elif config['Instruments']['std'] == '3458A':
        print("STD [ohms] {:5.8f}".format(float(std_readings[-1].strip())))
    return
#-------------------------------------------------------------------------------
# função ler_std()
# aceita como parâmetro o vetor com as leituras do objeto
# escreve na tela a última leitura da saída do TC objeto
def print_dut(dut_readings):
    if config['Instruments']['dut'] == '182A':
        print("DUT [mV] {:5.6f}".format(float(dut_readings[-1].replace('NDCV','').strip())*1000)) 
    elif config['Instruments']['dut'] == '2182A':
        print("DUT [mV] {:5.6f}".format(float(dut_readings[-1].strip())*1000))
    elif config['Instruments']['dut'] == '53132A':
        print("DUT [Hz] {:5.8f}".format(float(dut_readings[-1].strip())))
    elif config['Instruments']['dut'] == '3458A':
        print("DUT [ohms] {:5.8f}".format(float(dut_readings[-1].strip())))
    return
#-------------------------------------------------------------------------------
# função aquecimento()
# aceita como parâmetro o tempo de aquecimento, em segundos
def aquecimento(tempo):
    # executa o aquecimento, mantendo a tensão nominal aplicada pelo tempo
    # (em segundos) definido na variavel "tempo"
    dc_source.write("OUT +{:.6f} V".format(vdc_nominal));
    dc_source.write("OUT 0 HZ");
    # AC-AC
    #dc_source.write("OUT 1000 HZ");
    sw.write_raw(dc);
    espera(tempo);
    return
#-------------------------------------------------------------------------------
# função n_measure()
# aceita o número de repetições como parâmetro de entrada
# número de repetições DEVE ser par!
# se não for, será executada uma repetição a mais. p. ex.: 3 -> 4
# executa a medição do coeficiente de linearidade "n" do padrão e do objeto
# o algoritmo consiste em aplicar a tensão nominal, a tensão nominal + 1% e
# a tensão nominal -1%, registrando os respectivos valores de saída de padrão
# e objeto
def n_measure(M):
    # testa se M é par, se não for, soma 1 para se tornar par
    if int(M) % 2 != 0:
        M += 1;
    # define as variáveis que armazenam as leituras do padrão e do objeto
    std_readings = []
    dut_readings = []
    # variavel da constante V0 / (Vi-V0)
    k = []
    # aplica o valor nominal de tensão
    ac_source.write("OUT {:.6f} V".format(vac_nominal));
    ac_source.write("OUT "+str(freq)+" HZ");
    dc_source.write("OUT +{:.6f} V".format(vdc_nominal));
    espera(2); # espera 2 segundos
    sw.write_raw(dc);
    print("Vdc nominal: +{:.6f} V".format(vdc_nominal))
    # aguarda pelo tempo de espera configurado
    espera(wait_time);
    # lê as saídas de padrão e objeto, e armazena na variável std_readings e
    # dut_readings
    std_readings.append(ler_std())
    dut_readings.append(ler_dut())
    print_std(std_readings);
    print_dut(dut_readings);

    for i in range(1,M+1):
        # determina se i é par ou ímpar
        # se i é impar, v_i = 1,01*vdc_nominal
        # se i é par, v_i = 0,99*vdc_nominal
        if int(i) % 2 == 0:
            Vi = 0.99*vdc_nominal;
            k.append(-100);
        else:
            Vi = 1.01*vdc_nominal;
            k.append(100);

        sw.write_raw(ac);
        espera(2); # esperar 2 segundos
        dc_source.write("OUT +{:.6f} V".format(Vi));
        espera(2); # esperar 2 segundos
        sw.write_raw(dc);
        print("Vdc nominal + 1%: +{:.6f} V".format(Vi));
        # aguarda pelo tempo de espera configurado
        espera(wait_time);
        # lê as saídas de padrão e objeto, e armazena na variável std_readings e
        # dut_readings
        std_readings.append(ler_std())
        dut_readings.append(ler_dut())
        print_std(std_readings);
        print_dut(dut_readings);

    # cálculo do n
    sw.write_raw(ac); # mantém chave em ac durante cálculo

    if config['Instruments']['std'] == '182A':
        X0 = float(std_readings[0].replace('NDCV','').strip())
    else:
        X0 = float(std_readings[0].strip())

    if config['Instruments']['dut'] == '182A':
        Y0 = float(dut_readings[0].replace('NDCV','').strip())
    else:
        Y0 = float(dut_readings[0].strip())
        
    del std_readings[0]
    del dut_readings[0]

    if config['Instruments']['std'] == '182A':  
        Xi = numpy.array([float(a.replace('NDCV','').strip()) for a in std_readings]);
    else:
        Xi = numpy.array([float(a.strip()) for a in std_readings]);

    if config['Instruments']['dut'] == '182A':
        Yi = numpy.array([float(a.replace('NDCV','').strip()) for a in dut_readings]);
    else:
        Yi = numpy.array([float(a.strip()) for a in dut_readings]);

    nX = (Xi/X0 - 1) * k;
    nY = (Yi/Y0 - 1) * k;

    results = [numpy.mean(nX), numpy.std(nX, ddof=1), numpy.mean(nY), numpy.std(nY, ddof=1)];

    # retorna uma lista com vários arrays
    # o array results contém os resultados (média e desvio padrão de nX e nY)
    return {'results':results, 'Xi':Xi, 'X0':X0, 'Yi':Yi, 'Y0':Y0, 'k':k, 'nX':nX, 'nY':nY}
    
#-------------------------------------------------------------------------------
# função measure(vdc_atual, vac_atual, ciclo_ac)
# Executa os ciclos de medição, na sequência AC, +DC, AC, -DC e AC.
# aceita como parâmetros de entrada:
# vdc_atual - valor atual da tensão DC
# vac_atual - valor atual da tensão AC
# ciclo_ac - valor das leituras do último ciclo AC da medida anterior
# se não for a primeira medição, o primeiro ciclo AC aproveita as leituras do
# último ciclo AC da medição anterior
def measure(vdc_atual,vac_atual,ciclo_ac):
    # inicializa arrays de resultados
    std_readings = []
    dut_readings = []
    # configuração da fonte AC
    ac_source.write("OUT {:.6f} V".format(vac_atual));
    ac_source.write("OUT "+str(freq)+" HZ");
    # configuração da fonte DC
    dc_source.write("OUT +{:.6f} V".format(vdc_atual));
    dc_source.write("OUT 0 HZ");
    # ac-ac
    #dc_source.write("OUT 1000 HZ");
    # Iniciar medição
    espera(2); # esperar 2 segundos
    # Ciclo AC
    # testa se existem dados do último ciclo AC da medição anterior
    if (ciclo_ac == []):
        # caso negativo, medir AC normalmente
        sw.write_raw(ac);
        print("Ciclo AC")
        espera(wait_time);
        # leituras
        std_readings.append(ler_std())
        dut_readings.append(ler_dut())
        print_std(std_readings);
        print_dut(dut_readings);
    else:
        # caso positivo, aproveitar as medições do ciclo anterior
        print("Ciclo AC")
        std_readings.append(ciclo_ac[0])
        dut_readings.append(ciclo_ac[1])
        print_std(std_readings);
        print_dut(dut_readings);
    # Ciclo DC
    sw.write_raw(dc);
    print("Ciclo +DC")
    espera(wait_time);
    std_readings.append(ler_std())
    dut_readings.append(ler_dut())
    print_std(std_readings);
    print_dut(dut_readings);
    # Ciclo AC
    sw.write_raw(ac);
    print("Ciclo AC")
    espera(wait_time/2);
    # Mudar fonte DC para -DC
    dc_source.write("OUT -{:.6f} V".format(vdc_atual));
    espera(wait_time/2);
    std_readings.append(ler_std())
    dut_readings.append(ler_dut())
    print_std(std_readings);
    print_dut(dut_readings);
    # Ciclo -DC
    sw.write_raw(dc);
    print("Ciclo -DC")
    espera(wait_time);
    std_readings.append(ler_std())
    dut_readings.append(ler_dut())
    print_std(std_readings);
    print_dut(dut_readings);
    # Ciclo AC
    sw.write_raw(ac);
    print("Ciclo AC")
    espera(wait_time/2);
    # Mudar fonte DC para +DC
    dc_source.write("OUT +{:.6f} V".format(vdc_atual));
    espera(wait_time/2);
    std_readings.append(ler_std())
    dut_readings.append(ler_dut())
    print_std(std_readings);
    print_dut(dut_readings);
    # retorna as leituras obtidas para o objeto e para o padrão
    return {'std_readings':std_readings, 'dut_readings':dut_readings}
#-------------------------------------------------------------------------------
# função acdc_calc(readings,N,vdc_atual)
# Calcula a diferença AC-DC a partir dos dados obtidos com a funcao measure()
# aceita como parâmetros de entrada:
# readings - array com as leituras obtidas para o padrão e para o objeto
# N - vetor com os valores calculados de N (padrão e objeto)
# vdc_atual - valor de tensão DC ajustado para o último ciclo.
def acdc_calc(readings,N,vdc_atual):
    # x -> padrao; y -> objeto
    print("Calculando diferença ac-dc...")
    n_X = N[0]; # n do padrão
    n_Y = N[2]; # n do objeto
    # extrai os dados de leituras do padrão
    if config['Instruments']['std'] == '182A':
        x = numpy.array([float(a.replace('NDCV','').strip()) for a in readings['std_readings']]);
    else:
        x = numpy.array([float(a.strip()) for a in readings['std_readings']]);
    # extrai os dados de leitura do objeto
    if config['Instruments']['dut'] == '182A':
        y = numpy.array([float(a.replace('NDCV','').strip()) for a in readings['dut_readings']])
    else:
        y = numpy.array([float(a.strip()) for a in readings['dut_readings']])
    # calcula Xac, Xdc, Yac e Ydc a partir das leituras brutas    
    Xac = numpy.mean(numpy.array([x[0], x[2], x[4]]));     # AC médio padrão
    Xdc = numpy.mean(numpy.array([x[1], x[3]]));           # DC médio padrão
    Yac = numpy.mean(numpy.array([y[0], y[2], y[4]]));     # AC médio objeto
    Ydc = numpy.mean(numpy.array([y[1], y[3]]));           # DC médio objeto
    # Variáveis auxiliares X e Y
    X = Xac/Xdc - 1;
    Y = Yac/Ydc - 1;
    # diferença AC-DC medida:
    delta_m = 1e6 * ((X/n_X - Y/n_Y)/(1 + Y/n_Y));
    # critério para repetir a medição - diferença entre Yac e Ydc    
    if config['Instruments']['dut'] == '53132A':
        Delta = Yac - Ydc;
    elif config['Instruments']['dut'] == '3458A':
        Delta = Yac - Ydc;
    else:
        Delta = 1e6 * (Yac - Ydc);
    # ajuste da tensão DC para o próximo ciclo
    adj_dc = vdc_atual * (1 + (Yac - Ydc)/(n_Y * Ydc));
    # timestamp de cada medição
    date = datetime.datetime.now();
    timestamp = datetime.datetime.strftime(date, '%d/%m/%Y %H:%M:%S');
    # retorna lista com os arrays de leitura do padrão, objeto, a diferença ac-dc,
    # Delta=Yac-Ydc, o ajuste DC e o horário
    return {'std_readings':x,'dut_readings':y,'dif':delta_m, 'Delta':Delta, 'adj_dc':adj_dc,'timestamp':timestamp}
#-------------------------------------------------------------------------------
# função equilibrio()
# Calcula a tensão de equilíbrio AC no início da sequência de medições
# A função não aceita parâmetros de entrada
def equilibrio():
    dut_readings = []
    ac_source.write("OUT "+str(freq)+" HZ");
    dc_source.write("OUT {:.6f} V".format(vdc_nominal));
    espera(5) # aguarda 5 segundos antes de iniciar equilibrio
        
    # Aplica o valor nominal
    sw.write_raw(dc);
    print("Vdc nominal: +{:.6f} V".format(vdc_nominal))
    espera(wait_time/2);
    ac_source.write("OUT {:.6f} V".format(0.999*vac_nominal));
    espera(wait_time/2);
    dut_readings.append(ler_dut())
    print_dut(dut_readings);
    # Aplica Vac - 0.1%
    print("Vac nominal - 0.1%: +{:.6f} V".format(0.999*vac_nominal))
    sw.write_raw(ac);
    espera(wait_time)
    dut_readings.append(ler_dut())
    print_dut(dut_readings);
    sw.write_raw(dc);
    espera(2);
    ac_source.write("OUT {:.6f} V".format(1.001*vac_nominal));
    espera(2);
    # Aplica Vac + 0.1%
    print("Vac nominal + 0.1%: +{:.6f} V".format(1.001*vac_nominal))
    sw.write_raw(ac);
    espera(wait_time)
    dut_readings.append(ler_dut())
    print_dut(dut_readings);
    sw.write_raw(dc);
    # cálculo do equilíbrio
    yp = [0.999*vac_nominal, 1.001*vac_nominal]
    
    if config['Instruments']['dut'] == '182A':
        xp = [float(dut_readings[1].replace('NDCV','').strip()), float(dut_readings[2].replace('NDCV','').strip())]
        xi = float(dut_readings[0].replace('NDCV','').strip())
    else:
        xp = [float(dut_readings[1].strip()), float(dut_readings[2].strip())]
        xi = float(dut_readings[0].strip())
    # calcula o valor de equilíbrio através de interpolação linear    
    new_ac = numpy.interp(xi,xp,yp);
    # retorna o novo valor de AC
    return new_ac
#-------------------------------------------------------------------------------
# função stop_instruments()
# função chamada para interromper a medição
# não aceita parâmetros de entrada
# coloca as fontes em stand-by
def stop_instruments():
    sw.write_raw(reset);
    espera(1)
    ac_source.write("STBY");
    dc_source.write("STBY");
    return
#-------------------------------------------------------------------------------
# função criar_registro()
# Cria um novo registro de medição
# Não aceita parâmetros de entrada
def criar_registro():
    date = datetime.datetime.now();
    timestamp_file = datetime.datetime.strftime(date, '%d-%m-%Y_%Hh%Mm');
    timestamp_registro = datetime.datetime.strftime(date, '%d/%m/%Y %H:%M:%S');
    # o nome do registro é criado de forma automática, a partir da data e hora atuais
    registro_filename = "registro_"+timestamp_file+".csv"
    with open(registro_filename,"w") as csvfile:
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
    return registro_filename
#-------------------------------------------------------------------------------
# função registro_frequencia(egistro_filename,frequencia,n_value,vac_equilibrio)
# Inicia uma nova frequência no registro de medição
# Aceita os parâmetros
# registro_filename - o nome do registro criado com a função criar_registro()
# frequencia - o valor da frequência que está sendo medida no momento;
# n_value - os valores obtidos de n para padrão e objeto
# vac_equilibrio - a tensão AC de equilíbrio calculada com a funcao equilibrio()
# n_array:
# {'results':results, 'Xi':Xi, 'X0':X0, 'Yi':Yi, 'Y0':Y0, 'k':k, 'nX':nX, 'nY':nY}
def registro_frequencia(registro_filename,frequencia,n_array,vac_equilibrio):
    with open(registro_filename,"a") as csvfile:
        registro = csv.writer(csvfile, delimiter=';',lineterminator='\n')
        registro.writerow(['Tensão [V]',config['Measurement Config']['voltage'].replace('.',',')]);
        registro.writerow(['Frequência [kHz]',frequencia.replace('.',',')]);
        registro.writerow([' ']); # pular linha
        registro.writerow(['X0',str(n_array['X0']).replace('.',',')]); # valor de X0
        registro.writerow(['Xi'] + [str(i).replace('.',',') for i in n_array['Xi']]); # valores de Xi
        registro.writerow(['k'] + [str(i).replace('.',',') for i in n_array['k']]); # valores de k
        registro.writerow(['nX'] + [str(i).replace('.',',') for i in n_array['nX']]); # valores de nX
        registro.writerow(['nX (média)',str(n_array['results'][0]).replace('.',',')]); # Valor médio de nX
        registro.writerow(['nX (desvio padrão)',str(n_array['results'][1]).replace('.',',')]); # desvio padrão de nX
        registro.writerow([' ']); # pular linha
        registro.writerow(['Y0',str(n_array['Y0']).replace('.',',')]); # valor de X0
        registro.writerow(['Yi'] + [str(i).replace('.',',') for i in n_array['Yi']]); # valores de Yi
        registro.writerow(['k'] + [str(i).replace('.',',') for i in n_array['k']]); # valores de k
        registro.writerow(['nY'] + [str(i).replace('.',',') for i in n_array['nY']]); # valores de nY
        registro.writerow(['nY (média)',str(n_array['results'][2]).replace('.',',')]); # valor médio de nY
        registro.writerow(['nY (desvio padrão)',str(n_array['results'][3]).replace('.',',')]); # desvio padrão de nY
        registro.writerow([' ']); # pular linha
        registro.writerow(['Vac equilíbrio [V]',str(vac_equilibrio).replace('.',',')]); # Vac calculado para o equilíbrio
        registro.writerow([' ']); # pular linha
        # cabeçalho da tabela de medicao
        registro.writerow(['Data / hora','AC (STD)','AC (DUT)','DC+ (STD)','DC+ (DUT)','AC (STD)','AC (DUT)','DC- (STD)','DC- (DUT)','AC (STD)','AC (DUT)', 'Diferença', 'Delta', 'Tensão DC Aplicada','Temperatura [ºC]', 'Umidade Relativa [% u.r.]', 'Pressão Atmosférica [hPa]']);
    csvfile.close();
    return
#-------------------------------------------------------------------------------
# função registro_linha(registro_filename,results,vdc_atual)
# salva uma nova linha (medição individual) no registro de medição
# parâmetros:
# registro_filename - o nome do registro criado com a função criar_registro()
# results - array com os resultados
# vdc_atual - tensão DC calculada para a medição atual
def registro_linha(registro_filename,results,vdc_atual,ca_data):
    # results -> results['std_readings'], results['dut_readings'], results['dif'], results['Delta'], results['adj_dc'] e results['timestamp']
    with open(registro_filename,"a") as csvfile:
        registro = csv.writer(csvfile, delimiter=';',lineterminator='\n')
        registro.writerow([results['timestamp'],str(results['std_readings'][0]).replace('.',','),str(results['dut_readings'][0]).replace('.',','),str(results['std_readings'][1]).replace('.',','),str(results['dut_readings'][1]).replace('.',','),str(results['std_readings'][2]).replace('.',','),str(results['dut_readings'][2]).replace('.',','),str(results['std_readings'][3]).replace('.',','),str(results['dut_readings'][3]).replace('.',','),str(results['std_readings'][4]).replace('.',','),str(results['dut_readings'][4]).replace('.',','),str(results['dif']).replace('.',','),str(results['Delta']).replace('.',','),str(vdc_atual).replace('.',','),str(ca_data.temperature).replace('.',','),str(ca_data.humidity).replace('.',','),str(ca_data.pressure).replace('.',',')]);

    csvfile.close();
    return
#-------------------------------------------------------------------------------
# função registro_media(registro_filename,diferenca):
# finaliza o registro de medição para cada frequência, escrevendo a média
# e desvio padrão obtidos.
# Aceita os parâmetros:
# registro_filename - o nome do registro criado com a função criar_registro()
# diferenca - array com a média e o desvio padrão calculados
def registro_media(registro_filename,diferenca):
    with open(registro_filename,"a") as csvfile:
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
        print("Inicializando BME280 (condições ambientais)")
        bme280_init()
        print("Inicializando os intrumentos...")
        instrument_init()  # inicializa os instrumentos
        print("Colocando fontes em OPERATE...")
        meas_init()        # inicializa a medição (coloca fontes em operate)
        print("Criando arquivo de registro...")
        filename = criar_registro();  # cria arquivo de registro
        print("Arquivo "+filename+" criado com sucesso!")
        print("Aquecimento...");   
        aquecimento(heating_time);  # inicia o aquecimento
        # fazer loop para cada valor de frequencia
        for value in freq_array:
            freq = float(value) * 1000;
            print("Iniciando a medição...")
            print("V nominal: {:5.2f} V, f nominal: {:5.2f} Hz".format(vdc_nominal,freq));
            print("Medindo o N...");           
            n_array = n_measure(4);  # 4 repetições para o cálculo do N
            n_value = n_array['results'];
            print("N STD (média): {:5.2f}".format(n_value[0]))
            print("N STD (desvio padrão): {:5.2f}".format(n_value[1]))
            print("N DUT (média): {:5.2f}".format(n_value[2]))
            print("N DUT (desvio padrão): {:5.2f}".format(n_value[3]))   
            print("Equilibrio AC...");
            vac_atual = equilibrio();  # calcula a tensão AC de equilíbrio
            print("Vac aplicado: {:5.6f} V".format(vac_atual))
            registro_frequencia(filename,value,n_array,vac_atual);  # inicia o registro para a frequencia atual
            first_measure = True;   # flag para determinar se é a primeira repeticao

            if vac_atual > 1.1*vac_nominal:  # verifica se a tensão AC de equilíbrio não é muito elevada
                raise NameError('Tensão AC ajustada perigosamente alta!')
            
            print("Iniciando medição...");
            diff_acdc = [];
            Delta = [];
            vdc_atual = vdc_nominal;
            i = 0;
            while (i < repeticoes):  # inicia as repetições da medição
                print ("Vdc aplicado: {:5.6f} V".format(vdc_atual))
                if first_measure:    # testa se é a primeira medição
                    ciclo_ac = [];
                    first_measure = False
                else:
                    ciclo_ac = [readings['std_readings'][4], readings['dut_readings'][4]];  # caso não seja, aproveitar o último ciclo AC
                readings = measure(vdc_atual,vac_atual,ciclo_ac);                           # da repetição anterior
                results = acdc_calc(readings,n_value,vdc_atual);                            # calcula a diferença ac-dc         
                print("Diferença ac-dc: {:5.2f}".format(results['dif']))               
                print("Delta: {:5.2f}".format(results['Delta']))
                print("Data / hora: "+results['timestamp']);
                ca_data = bme280_read();
                print("Temperatura: "+str(ca_data.temperature)+" ºC");
                print("Umidade Relativa: "+str(ca_data.humidity)+" %u.r.");
                print("Pressão atmosférica: "+str(ca_data.pressure)+" hPa");
                if abs(results['Delta']) > 50:               # se o ponto não passa no critério de descarte, repetir medição
                    print("Delta > 50. Ponto descartado!")
                else:
                    diff_acdc.append(results['dif']);
                    Delta.append(results['Delta']);
                    registro_linha(filename,results,vdc_atual,ca_data);
                    i += 1;               
                vdc_atual = results['adj_dc'];              # aplica o ajuste DC
                if vdc_atual > 1.1*vdc_nominal:
                    raise NameError('Tensão DC ajustada perigosamente alta!')    

            print("Medição concluída.")                      
        
            print("Resultados:")
            print("Média: {:5.2f}".format(numpy.mean(diff_acdc)))
            print("Desvio padrão: {:5.2f}".format(numpy.std(diff_acdc, ddof=1)))
            print("Salvando arquivo...")
            registro_media(filename,diff_acdc);             # salva a diferença ac-dc média para a frequência atual no registro

        stop_instruments();                                 # coloca as fontes em stand-by
        print("Concluído.")
                
    except:
        stop_instruments()
        import traceback
        traceback.print_exc()
        

# execução do programa principal
if __name__ == '__main__':
    main()
