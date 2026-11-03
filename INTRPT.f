      DIMENSION HX(7),HY(7),HR(7)
      IX=1969
      N=40
      S=.16
      AL=.2
      X0=1.05
      Y0=3.
      CALL PLOTS(0,0,0)
      DO 10 K=1,7
      CALL RANDU(IX,IY,R)
      IX=IY
      HX(K)=X0+R*S*FLOAT(N)
      CALL RANDU(IX,IY,R)
      IX=IY
      HY(K)=Y0+R*S*FLOAT(N)
      CALL RANDU(IX,IY,R)
      IX=IY
   10 HR(K)=.3+R*.7
      DO 40 J=1,N
      DO 30 II=1,N
      I=II
      IF(MOD(J,2).EQ.0) I=N+1-II
      X=X0+FLOAT(I-1)*S
      Y=Y0+FLOAT(J-1)*S
      CALL RANDU(IX,IY,R)
      IX=IY
      A=R*3.14159
      CALL RANDU(IX,IY,R)
      IX=IY
      IF(R.LT..03) GO TO 30
      DO 20 K=1,7
      D=SQRT((X-HX(K))**2+(Y-HY(K))**2)/HR(K)
      IF(D.LT..6+.8*R) GO TO 30
   20 CONTINUE
      DX=.5*AL*COS(A)
      DY=.5*AL*SIN(A)
      CALL PLOT(X-DX,Y-DY,3)
      CALL PLOT(X+DX,Y+DY,2)
   30 CONTINUE
   40 CONTINUE
      CALL PLOT(0.,0.,999)
      STOP
      END
