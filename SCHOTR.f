      DIMENSION CX(4),CY(4)
      DATA CX/-.5,.5,.5,-.5/,CY/-.5,-.5,.5,.5/
      IX=65539
      S=0.5
      CALL PLOTS(0,0,0)
      DO 30 J=1,22
      T=FLOAT(J-1)/21.
      DO 20 I=1,12
      CALL RANDU(IX,IY,R)
      IX=IY
      A=(R-.5)*T*1.4
      CALL RANDU(IX,IY,R)
      IX=IY
      DX=(R-.5)*T*.6
      CALL RANDU(IX,IY,R)
      IX=IY
      DY=(R-.5)*T*.6
      XC=(FLOAT(I)+DX)*S+.75
      YC=(23.-FLOAT(J)+DY)*S+.5
      C=COS(A)
      SN=SIN(A)
      DO 10 K=1,5
      L=K
      IF(K.EQ.5) L=1
      X=XC+(CX(L)*C-CY(L)*SN)*S
      Y=YC+(CX(L)*SN+CY(L)*C)*S
      IPEN=2
      IF(K.EQ.1) IPEN=3
   10 CALL PLOT(X,Y,IPEN)
   20 CONTINUE
   30 CONTINUE
      CALL PLOT(0.,0.,999)
      STOP
      END
