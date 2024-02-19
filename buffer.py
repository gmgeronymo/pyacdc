# Programa para testar buffer
# Gean Marcos Geronymo
# 04/03/2022

# Carregar módulos
import visa
import numpy as np
import datetime
import time
import csv

# configuracoes
rm = visa.ResourceManager()
gpib_source = 5;
gpib_dvm = 22;
wait_time = 60;
registro_filename = 'output.csv';

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
# função instrument_init()
# inicializa a comunicação com os instrumentos, via GPIB
def instrument_init():
    # variáveis globais
    global source;
    global dvm;
    # Inicialização dos intrumentos conectados ao barramento GPIB
    print("Comunicando com fonte no endereço "+gpib_source+"...");
    source = rm.open_resource("GPIB0::"+gpib_source+"::INSTR");
    print(source.query("*IDN?"));
    print("OK!\n");

    print("Comunicando com o DVM no endereço "+gpib_dvm+"...");
    dvm = rm.open_resource("GPIB0::"+gpib_dvm+"::INSTR");
    
    dvm.write("OFORMAT ASCII")
    dvm.write("END ALWAYS")
    dvm.write("NPLC 8")

    print(dvm.query("ID?"))
    print("OK!\n");
   
    return
#-------------------------------------------------------------------------------
# programa principal
#-------------------------------------------------------------------------------
def main():
    print("Inicializando os intrumentos...")
    instrument_init()  # inicializa os instrumentos
    # array com as tensoes de entrada
    voltage_array = np.arange(-3,3,0.025);

    for voltage in voltage_array:
        print("Iniciando a medição...")
        print("Tensão de entrada: {:5.3f} V".format(voltage));
        # aplicar a tensao
        source.write("OUT +{:.6f} V".format(voltage));
        source.write("OUT 0 HZ");
        # esperar 2 segundos
        espera(2); 
        source.write("*CLS");
        source.write("OPER");

        # esperar estabilizar
        espera(wait_time);

        # timestamp de cada medição
        date = datetime.datetime.now();
        timestamp = datetime.datetime.strftime(date, '%d/%m/%Y %H:%M:%S');

        # fazer a leitura
        # para valores menores que 1 V usar a faixa de 1 V
        if (voltage <= 1) :
            output = std.query("DCV 1");
        else:
            output = std.query("DCV 10");

        print (output);

        # salva no arquivo csv
        with open(registro_filename,"a") as csvfile:
            registro = csv.writer(csvfile, delimiter=';',lineterminator='\n')
            registro.writerow([timestamp,str(voltage).replace('.',','),str(output).replace('.',',')]);

        csvfile.close();

        # espera 2 segundos
        espera(2); 
    

# execução do programa principal
if __name__ == '__main__':
    main()

