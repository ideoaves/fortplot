      IX=5
      NB=300
      R=450.
      U=2.25/R
      CX=4.25
      CY=6.25
      SP=2.2
      PT=2.
      PV=.3*R
      PC=1.63/R
      PK=1./(.9*R)
      CALL PLOTS(0,0,0)
      DO 40 N=1,NB
   10 CALL RANDU(IX,IY,X)
      IX=IY
      CALL RANDU(IX,IY,Y)
      IX=IY
      X=(2.*X-1.)*R
      Y=(2.*Y-1.)*R
      IF(X*X+Y*Y.GT.R*R) GO TO 10
      CALL RANDU(IX,IY,V)
      IX=IY
      CALL RANDU(IX,IY,W)
      IX=IY
      NL=7+INT(4.*W)
      CALL RANDU(IX,IY,A)
      IX=IY
      AL=(10.+50.*A)*PT
      D=Y-(PV+PC*X*X)
      IF(D.GT.0.) AL=AL*AMAX1(.1,1.-PK*D)
      DO 30 I=1,NL
      T=(FLOAT(I)-.5*FLOAT(NL+1))*SP
      S=.5*AL
      IF(MOD(I,2).EQ.0) S=-S
      IPEN=2
      IF(I.EQ.1) IPEN=3
      IF(V.LT..5) GO TO 20
      CALL PLOT(CX+(X-S)*U,CY+(Y+T)*U,IPEN)
      CALL PLOT(CX+(X+S)*U,CY+(Y+T)*U,2)
      GO TO 30
   20 CALL PLOT(CX+(X+T)*U,CY+(Y-S)*U,IPEN)
      CALL PLOT(CX+(X+T)*U,CY+(Y+S)*U,2)
   30 CONTINUE
   40 CONTINUE
      CALL PLOT(0.,0.,999)
      STOP
      END
