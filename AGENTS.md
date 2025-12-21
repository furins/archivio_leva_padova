

# Project Overview

Sto realizzando uno scraper che permette di recuperare informazioni su persone vissute nel passato che sono state in qualche modo registrate nell'archivio di leva militare di padova.

La pagina internet a cui si accede attraverso un'area riservata presenta un form di ricerca con due campi obbligatori e esporta i risultati in una tabella. Il codice ha grossomodo questa struttura:

<div class="col-md-6 col-md-offset-3">
	
	<div class="text-center">
		<strong>Ricerca per:</strong><br><br><i>Selezionate i campi da ricercare:<br> 
			(* cognome e nome sono obbligatori)</i><br><br>		
	</div>
	
	<form id="form1" name="form1" method="post">
		<input type="hidden" name="ricerca" value="si">
		<table cellpadding="5px" style="width:100%">
			<tr>
				<td><strong>Cognome *</strong></td>
				<td><input class="form-control input-sm" type="text" name="cognome" placeholder="Simile a"
					value="CAMIN"></td>
			</tr>
			<tr style="height:5px;"></tr>
			<tr>
				<td><strong>Nome *</strong></td>
				<td><input class="form-control input-sm" type="text" name="nome"  placeholder="Simile a"
					value="Francesco"></td>
			</tr>
			<tr style="height:5px;"></tr>
			<tr>
				<td>Madre</td>
				<td><input class="form-control input-sm" type="text" name="madre" placeholder="Simile a"
					value=""></td>
			</tr>
			<tr style="height:5px;"></tr>
			<tr>
				<td>Località nascita</td>
				<td><input class="form-control input-sm" type="text" name="localita"  placeholder="Simile a"
					value=""></td>
			</tr>
			<tr style="height:5px;"></tr>
			<tr>
				<td>Nati nel</td>
				<td><input class="form-control input-sm" type="text" name="nascita" maxlength="4" placeholder="aaaa" 
					value=""></td>
			</tr>
			<tr style="height:5px;"></tr>
			<tr>
				<td>Nati il</td>
				<td>
					<input class="form-control input-sm" type="text" name="giorno" maxlength="2" placeholder="gg" style="width:40px; display:inline;"
						value=""> / 
					<input class="form-control input-sm" type="text" name="mese" maxlength="2" placeholder="mm" style="width:45px; display:inline;"
						value=""> / 
					<input class="form-control input-sm" type="text" name="anno" maxlength="4" placeholder="aaaa" style="width:70px; display:inline;"
						value=""></td>
			</tr>
			<tr style="height:25px;"></tr>
			<tr>
				<td><strong>Ordina per:</strong></td>
				<td>
					<select name="ord" class="form-control input-sm" >
						<option value="cognome" selected>Cognome</option>
						<option value="nome" > Nome</option>
						<option value="nascita" > Data nascita</option>
						<option value="localita" > Località nascita</option>
						<option value="comune" > Comune Iscrizione</option>
					</select>
				</td>
			</tr>
			<tr style="height:25px;"></tr>
			<tr>
				<td></td>
				<td><input type="button" name="leva" class="btn btn-sm btn-primary" value="Esegui ricerca" onclick="javascript:checkForm('form1');"></td>
			</tr>
		</table>
	</form>
</div>
		
<div class="col-md-12"><br><strong>11 risultati trovati</strong><br><br><br>
		<div class="table-flex">
			<table class="table table-condensed table-striped table-risultati">
				<thead>
					<tr>	
						<th>Cognome</th>
						<th>Nome</th>
						<th>Num. lista</th>
						<th>Data di Nascita</th>
						<th>Località Nascita</th>
						<th>Provincia</th>
						<th>Anno</th>
						<th>Comune Iscrizione</th>
						<th>Mandamento</th>
						<th>Padre</th>
						<th>Madre</th>
					</tr>
				</thead>
				<tbody>
	
			<tr>
				<td data-title="Cognome">CAMIN</td>
				<td data-title="Nome">Francesco</td>
				<td data-title="Num. lista">295,00</td>
				<td data-title="Data di Nascita">01/09/1890</td>
				<td data-title="Località Nascita">MASI</td>
				<td data-title="Provincia">PD</td>
				<td data-title="Anno">1890</td>
				<td data-title="Comune Iscrizione">MASI</td>
				<td data-title="Mand">MONTAGNANA</td>
				<td data-title="Padre">Luigi</td>
				<td data-title="Madre"></td>
			</tr>
		
			<tr>
				<td data-title="Cognome">CAMIN</td>
				<td data-title="Nome">Francesco</td>
				<td data-title="Num. lista">31,00</td>
				<td data-title="Data di Nascita">01/09/1891</td>
				<td data-title="Località Nascita">MASI</td>
				<td data-title="Provincia">PD</td>
				<td data-title="Anno">1891</td>
				<td data-title="Comune Iscrizione">PADOVA</td>
				<td data-title="Mand">MONTAGNANA</td>
				<td data-title="Padre">Luigi</td>
				<td data-title="Madre"></td>
			</tr>
		
			<tr>
				<td data-title="Cognome">CAMIN</td>
				<td data-title="Nome">Francesco</td>
				<td data-title="Num. lista">24,00</td>
				<td data-title="Data di Nascita">01/09/1890</td>
				<td data-title="Località Nascita">MASI</td>
				<td data-title="Provincia">PD</td>
				<td data-title="Anno">1892</td>
				<td data-title="Comune Iscrizione">MASI</td>
				<td data-title="Mand">MONTAGNANA</td>
				<td data-title="Padre">Luigi</td>
				<td data-title="Madre"></td>
			</tr>
		
			<tr>
				<td data-title="Cognome">CAMIN</td>
				<td data-title="Nome">Francesco</td>
				<td data-title="Num. lista">90,00</td>
				<td data-title="Data di Nascita">29/08/1875</td>
				<td data-title="Località Nascita">S.MARTINO DI VENEZZE</td>
				<td data-title="Provincia">RO</td>
				<td data-title="Anno">1875</td>
				<td data-title="Comune Iscrizione">S.MARTINO DI VENEZZE</td>
				<td data-title="Mand">ROVIGO</td>
				<td data-title="Padre">Angelo</td>
				<td data-title="Madre">Dicati Anna</td>
			</tr>
		
			<tr>
				<td data-title="Cognome">CAMINI</td>
				<td data-title="Nome">Francesco Luigi</td>
				<td data-title="Num. lista">147,00</td>
				<td data-title="Data di Nascita">23/02/1861</td>
				<td data-title="Località Nascita">FICAROLO</td>
				<td data-title="Provincia">RO</td>
				<td data-title="Anno">1861</td>
				<td data-title="Comune Iscrizione">STIENTA</td>
				<td data-title="Mand">OCCHIOBELLO</td>
				<td data-title="Padre">Gregorio</td>
				<td data-title="Madre">Antoniolli Filo</td>
			</tr>
		
			<tr>
				<td data-title="Cognome">CAMINI</td>
				<td data-title="Nome">Francesco</td>
				<td data-title="Num. lista">175,00</td>
				<td data-title="Data di Nascita">15/02/1857</td>
				<td data-title="Località Nascita">CASTELNOVO BARIANO</td>
				<td data-title="Provincia">RO</td>
				<td data-title="Anno">1857</td>
				<td data-title="Comune Iscrizione">CASTELNOVO BARIANO</td>
				<td data-title="Mand">MASSA SUPERIORE</td>
				<td data-title="Padre">Desiderio</td>
				<td data-title="Madre">Tonazzi Carola</td>
			</tr>
		
			<tr>
				<td data-title="Cognome">CAMINI</td>
				<td data-title="Nome">Francesco</td>
				<td data-title="Num. lista">304,00</td>
				<td data-title="Data di Nascita">21/10/1866</td>
				<td data-title="Località Nascita">GAIBA</td>
				<td data-title="Provincia">RO</td>
				<td data-title="Anno">1866</td>
				<td data-title="Comune Iscrizione">STIENTA</td>
				<td data-title="Mand">OCCHIOBELLO</td>
				<td data-title="Padre">Giulio</td>
				<td data-title="Madre">Poletto Rosa</td>
			</tr>
		
			<tr>
				<td data-title="Cognome">CAMINI</td>
				<td data-title="Nome">Francesco Giuseppe</td>
				<td data-title="Num. lista">93,00</td>
				<td data-title="Data di Nascita">02/01/1869</td>
				<td data-title="Località Nascita">TRECENTA</td>
				<td data-title="Provincia">RO</td>
				<td data-title="Anno">1869</td>
				<td data-title="Comune Iscrizione">TRECENTA</td>
				<td data-title="Mand">BADIA POLESINE</td>
				<td data-title="Padre">Vincenzo</td>
				<td data-title="Madre">Ganzarolli Doro</td>
			</tr>
		
			<tr>
				<td data-title="Cognome">CAMINI</td>
				<td data-title="Nome">Francesco</td>
				<td data-title="Num. lista">238,00</td>
				<td data-title="Data di Nascita">15/02/1871</td>
				<td data-title="Località Nascita">MASSA SUPERIORE</td>
				<td data-title="Provincia">RO</td>
				<td data-title="Anno">1871</td>
				<td data-title="Comune Iscrizione">MASSA SUPERIORE</td>
				<td data-title="Mand">MASSA SUPERIORE</td>
				<td data-title="Padre">Paolo</td>
				<td data-title="Madre">Pendanti Filome</td>
			</tr>
		
			<tr>
				<td data-title="Cognome">CAMINI</td>
				<td data-title="Nome">Vittorio Francesco</td>
				<td data-title="Num. lista">329,00</td>
				<td data-title="Data di Nascita">05/07/1885</td>
				<td data-title="Località Nascita">TRECENTA</td>
				<td data-title="Provincia">RO</td>
				<td data-title="Anno">1885</td>
				<td data-title="Comune Iscrizione">BADIA POLESINE</td>
				<td data-title="Mand">BADIA POLESINE</td>
				<td data-title="Padre">Nicola</td>
				<td data-title="Madre">Zanella Florind</td>
			</tr>
		
			<tr>
				<td data-title="Cognome">CAMINI</td>
				<td data-title="Nome">Francesco</td>
				<td data-title="Num. lista">328,00</td>
				<td data-title="Data di Nascita">02/01/1869</td>
				<td data-title="Località Nascita">TRECENTA</td>
				<td data-title="Provincia">RO</td>
				<td data-title="Anno">1882</td>
				<td data-title="Comune Iscrizione">BADIA POLESINE</td>
				<td data-title="Mand">BADIA POLESINE</td>
				<td data-title="Padre">Vincenzo</td>
				<td data-title="Madre">Ganzarollo Doro</td>
			</tr>
				
				</tbody>
			</table>
		</div>
	</div></div> 

Il programma deve avere il minor impatto possibile sul server, quindi deve utilizzare meccanismi di cache e di inferenza per ridurre al minimo le richieste.