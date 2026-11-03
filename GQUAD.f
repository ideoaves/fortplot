      IX=65539
      CALL PLOTS(0,0,0)
      DO 10 K=1,50
      CALL GAUSS(IX,1.1,4.,X)
      IF(X.LT..5) X=.5
      IF(X.GT.6.5) X=0.5
      Y=AMOD(.0145*FLOAT(K)**2,11.)+.75
      IPEN=2
      IF(K.EQ.1) IPEN=3
   10 CALL PLOT(X,Y,IPEN)
      CALL PLOT(0.,0.,999)
      STOP
      END
