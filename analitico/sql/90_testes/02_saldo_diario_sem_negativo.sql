-- Nenhum saldo de fim de dia pode ser negativo.
select * from marts.fato_saldo_diario where saldo_fim_dia < 0
